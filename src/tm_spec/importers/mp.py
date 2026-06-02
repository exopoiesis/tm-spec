"""Import Materials Project entries into TM-Spec documents (the *magnetic depth*).

OPTIMADE gives structure *width* (``importers.optimade``); NOMAD gives method /
XC / energy *depth* (``importers.nomad``). Neither reliably carries the COMPUTED
magnetic ground state — magnetic ordering is not an OPTIMADE property, and most
NOMAD GGA archives omit a magnetic block. Materials Project does: its
``/materials/summary/`` endpoint exposes ``is_magnetic`` / ``ordering`` (NM / FM /
AFM / FiM) / ``total_magnetization`` / ``num_magnetic_sites``, and
``/materials/magnetism/`` exposes per-site ``magmoms``. This importer maps that
onto the TM-Spec ``magnetic`` block — the third leg that pairs with OPTIMADE width
and NOMAD depth via ``tm_spec.merge.merge_docs``.

Architecture (mirrors ``importers.nomad`` / ``importers.optimade``):

    MPClient                              thin stdlib/httpx client (X-API-KEY)
    summary_to_tm_spec(rec, magrec=...)   pure transform (mockable, offline)
    fetch_to_tm_spec(formula=..., ...)    network glue -> tm-spec doc(s)

CLI (dispatched from ``tm_spec.cli``):

    tm-spec import-mp --formula FeS2 [--space-group 205] [--material-id mp-226] \
        [--out FILE | --json]

Auth: the MP API needs a (free) key. It is read from the ``api_key`` argument or
the ``MP_API_KEY`` env var (never hardcoded). The endpoint sits behind Cloudflare,
which 403s the default urllib User-Agent (Error 1010) — we always send an explicit
User-Agent.

Honesty / caveats encoded in the output:
    * ``structure.geometry_origin = "dft_relaxed"`` (MP structures are VASP-relaxed).
    * MP reports only collinear ordering at 0 K; ``magnetic.collinear = true``.
    * MP's generic ``AFM`` does not name the A/C/G subtype -> mapped to ``AFM-G``
      with a ``surrogate_warning`` (MP's small-cell enumeration can also miss the
      true AFM order; the experimental anchor is MAGNDATA).
    * XC (GGA vs GGA+U) is the MP default and is NOT re-derived here -> noted in
      ``results.notes`` rather than fabricated into ``calculation.level``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import __version__ as TM_SPEC_VERSION

MP_API_BASE_DEFAULT = "https://api.materialsproject.org"
MP_API_BASE_ENV = "TM_SPEC_MP_API_BASE"
MP_API_KEY_ENV = "MP_API_KEY"
USER_AGENT = f"tm-spec/{TM_SPEC_VERSION} (+https://github.com/exopoiesis)"

# MP ``ordering`` -> TM-Spec ``magnetic_state`` enum
# {NM, FM, AFM-A, AFM-C, AFM-G, ferri, PM-itinerant}. MP does not report the AFM
# subtype, so plain AFM maps to the generic Neel ``AFM-G`` (flagged in surrogate_warning).
_MP_ORDERING_TO_STATE: dict[str | None, str | None] = {
    "NM": "NM",
    "FM": "FM",
    "FiM": "ferri",
    "FERRI": "ferri",
    "AFM": "AFM-G",
    "Unknown": None,
    None: None,
}

# The summary fields the importer relies on.
SUMMARY_FIELDS = [
    "material_id", "formula_pretty", "symmetry", "nsites",
    "is_magnetic", "ordering", "total_magnetization",
    "total_magnetization_normalized_formula_units", "num_magnetic_sites",
    "types_of_magnetic_species", "energy_above_hull", "is_stable",
]
MAGNETISM_FIELDS = ["material_id", "ordering", "total_magnetization", "magmoms", "num_magnetic_sites"]


class MPError(RuntimeError):
    """Raised on HTTP / parse / auth errors from the Materials Project API."""


# ---------------------------------------------------------------------------
# HTTP client


class MPClient:
    """Minimal stdlib client for the new Materials Project API (api.materialsproject.org).

    Parameters
    ----------
    api_key:
        MP API key. Falls back to the ``MP_API_KEY`` env var. Required (the MP
        API rejects unauthenticated requests).
    base_url:
        API root; override for testing. Defaults to ``MP_API_BASE`` env or the
        production endpoint.
    timeout_s:
        Per-request timeout.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 timeout_s: float = 30.0) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get(MP_API_KEY_ENV)
        self.base_url = (base_url or os.environ.get(MP_API_BASE_ENV) or MP_API_BASE_DEFAULT).rstrip("/")
        self.timeout_s = timeout_s

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise MPError(
                f"no MP API key (pass api_key= or set {MP_API_KEY_ENV}); the MP API rejects "
                "unauthenticated requests"
            )
        url = self.base_url + path + "?" + urllib.parse.urlencode(params, doseq=True)
        headers = {
            "X-API-KEY": self.api_key,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,  # Cloudflare 403s the default urllib UA (Error 1010)
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")[:300]
            except Exception:
                pass
            raise MPError(f"MP API GET {path} -> HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise MPError(f"MP API GET {path} -> network error: {exc}") from exc
        if not payload:
            return {}
        try:
            return json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MPError(f"MP API GET {path} -> invalid JSON: {exc}") from exc

    def summary(self, formula: str | None = None, chemsys: str | None = None,
                material_ids: str | None = None, fields: list[str] | None = None,
                limit: int = 100, sort_fields: str | None = "energy_above_hull",
                ) -> list[dict[str, Any]]:
        """GET /materials/summary/ filtered by formula / chemsys / material_ids.

        NOTE: ``magnetic_ordering`` is NOT an accepted query param on summary (HTTP
        400); pull then filter on the ``ordering`` field client-side.
        """
        params: dict[str, Any] = {"_fields": ",".join(fields or SUMMARY_FIELDS), "_limit": limit}
        if sort_fields:
            params["_sort_fields"] = sort_fields
        if formula:
            params["formula"] = formula
        if chemsys:
            params["chemsys"] = chemsys
        if material_ids:
            params["material_ids"] = material_ids
        return self._get("/materials/summary/", params).get("data", [])

    def magnetism(self, material_id: str, fields: list[str] | None = None) -> dict[str, Any]:
        """GET /materials/magnetism/ for one material_id (per-site magmoms)."""
        data = self._get("/materials/magnetism/", {
            "material_ids": material_id, "_fields": ",".join(fields or MAGNETISM_FIELDS),
        }).get("data", [])
        return data[0] if data else {}


# ---------------------------------------------------------------------------
# Pure transform: MP summary (+ magnetism) record -> TM-Spec doc


def _slug(s: str) -> str:
    """Make a string safe for the TM-Spec ``id`` pattern (mirror nomad/optimade)."""
    out = "".join(ch if (ch.isalnum() or ch in "_.+-") else "_" for ch in str(s))
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_") or "entry"


def _resolve_state(ordering: str | None, is_magnetic: Any, mabs: float | None,
                   n_mag: int | None) -> tuple[str, str | None]:
    """Map MP ordering onto a TM-Spec magnetic_state, returning (state, surrogate_warning)."""
    if ordering in _MP_ORDERING_TO_STATE and _MP_ORDERING_TO_STATE[ordering] is not None:
        state = _MP_ORDERING_TO_STATE[ordering]
        warn = None
        if ordering == "AFM":
            warn = (
                "MP reports generic AFM; subtype (A/C/G) unspecified -> mapped to AFM-G. "
                "MP collinear small-cell enumeration may also miss the true AFM order "
                "(experimental anchor: MAGNDATA)."
            )
        return state, warn  # type: ignore[return-value]
    # ordering missing / Unknown -> infer from the moment, and FLAG it.
    if mabs is not None:
        state = "FM" if (mabs / max(n_mag or 1, 1)) > 0.5 else "NM"
    else:
        state = "FM" if is_magnetic else "NM"
    return state, f"MP ordering={ordering!r}; state inferred from moment (mabs={mabs})."


def summary_to_tm_spec(
    summary_rec: dict[str, Any],
    magnetism_rec: dict[str, Any] | None = None,
    *,
    doc_id: str | None = None,
    date: str | None = None,
    author: str = "import@mp",
) -> dict[str, Any]:
    """Pure transformation: one MP ``/materials/summary/`` record (+ optional
    ``/materials/magnetism/`` record with ``magmoms``) -> a TM-Spec/0.3
    ``SinglePointCalculation`` doc carrying the COMPUTED ``magnetic`` block.

    No network. Tests feed in-memory MP-shaped dicts.
    """
    if not isinstance(summary_rec, dict):
        raise MPError(f"summary_rec must be a dict, got {type(summary_rec).__name__}")

    sym = summary_rec.get("symmetry") or {}
    mid = summary_rec.get("material_id") or "mp-unknown"
    formula = summary_rec.get("formula_pretty") or "Unknown"
    ordering = summary_rec.get("ordering")
    is_mag = summary_rec.get("is_magnetic")
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    mm = (magnetism_rec or {}).get("magmoms") or []
    mabs = sum(abs(float(x)) for x in mm) if mm else None
    n_mag = sum(1 for x in mm if abs(float(x)) > 0.3) if mm else None

    state, warn = _resolve_state(ordering, is_mag, mabs, n_mag)

    magnetic: dict[str, Any] = {"state": state, "collinear": True}
    if mm:
        magnetic["magmoms_uB"] = {str(i): round(float(x), 3) for i, x in enumerate(mm)}
    if warn:
        magnetic["surrogate_warning"] = warn

    if doc_id is None:
        doc_id = f"tm.mp.{_slug(mid)}.{date}"

    structure: dict[str, Any] = {
        "formula": formula,
        "chemical_formula_reduced": formula,
        "pbc": [True, True, True],
        "geometry_origin": "dft_relaxed",  # MP structures are DFT(VASP)-relaxed
    }
    if isinstance(sym.get("number"), int):
        structure["space_group"] = {"number": sym["number"]}

    doc: dict[str, Any] = {
        "spec": "tm-spec/0.3",
        "kind": "SinglePointCalculation",
        "id": doc_id,
        "schema_url": "https://exopoiesis.github.io/tm-spec/0.3.json",
        "structure": structure,
        "calculation": {"method": "DFT", "code": {"name": "VASP"}},
        "magnetic": magnetic,
        "results": {
            "status": "PRELIMINARY",
            "paper_quotable": False,
            "notes": (
                "Imported from Materials Project (computed magnetic ground state); "
                "XC = MP default GGA/GGA+U (not re-derived). Magnetic depth only."
            ),
        },
        "sanity": [
            {"id": "G09_geometry_origin",
             "rule": "geometry_origin is dft_relaxed/dft_static, not an MLIP geometry",
             "observed": "dft_relaxed", "pass": True},
        ],
        "provenance": {
            "date": date,
            "author": author,
            "import_source": {
                "archive": "materials_project",
                "entry_id": mid,
                "url": f"https://next-gen.materialsproject.org/materials/{mid}",
                "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "importer": f"tm-spec import-mp@{TM_SPEC_VERSION}",
                "raw_keys": ["summary.ordering", "summary.is_magnetic",
                             "summary.total_magnetization", "magnetism.magmoms",
                             "symmetry.number", "formula_pretty"],
            },
            "compute": {"host": "mp-api", "cost_usd": 0.0},
        },
    }
    return doc


# ---------------------------------------------------------------------------
# Network glue


def fetch_to_tm_spec(
    *,
    formula: str | None = None,
    space_group: int | None = None,
    material_id: str | None = None,
    client: MPClient | None = None,
    api_key: str | None = None,
    date: str | None = None,
    author: str = "import@mp",
    with_magmoms: bool = True,
) -> list[dict[str, Any]]:
    """Fetch MP magnetism and convert to TM-Spec doc(s).

    Provide ``material_id`` (exact) OR ``formula`` (optionally narrowed to one
    ``space_group``). Returns a list of docs (one per matched material; for a
    formula query the most stable polymorph per space group, else all matches).
    """
    cli = client or MPClient(api_key=api_key)
    if material_id:
        rows = cli.summary(material_ids=material_id)
    elif formula:
        rows = cli.summary(formula=formula, limit=500)
        if space_group is not None:
            rows = [d for d in rows if (d.get("symmetry") or {}).get("number") == space_group]
            rows.sort(key=lambda d: (d.get("energy_above_hull") if d.get("energy_above_hull") is not None else 9e9))
            rows = rows[:1]  # most stable polymorph at this space group
    else:
        raise MPError("need material_id or formula to fetch from MP")

    docs: list[dict[str, Any]] = []
    for rec in rows:
        magrec = cli.magnetism(rec.get("material_id")) if (with_magmoms and rec.get("material_id")) else None
        docs.append(summary_to_tm_spec(rec, magrec, date=date, author=author))
    return docs


# ---------------------------------------------------------------------------
# YAML emission + CLI (mirror nomad/optimade)


def _to_yaml(doc: dict[str, Any]) -> str:
    import yaml
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="tm-spec import-mp",
        description="Import Materials Project computed magnetism into TM-Spec doc(s).",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--material-id", help="exact MP id, e.g. mp-226")
    g.add_argument("--formula", help="reduced/pretty formula, e.g. FeS2")
    p.add_argument("--space-group", type=int, default=None, help="narrow formula query to one space group")
    p.add_argument("--out", "-o", type=Path, default=None, help="output YAML path (default: stdout)")
    p.add_argument("--json", action="store_true", help="emit JSON instead of YAML")
    p.add_argument("--api-base", default=None)
    p.add_argument("--api-key", default=None, help="MP API key (default: MP_API_KEY env)")
    p.add_argument("--author", default="import@mp")
    args = p.parse_args(argv)

    client = MPClient(api_key=args.api_key, base_url=args.api_base)
    try:
        docs = fetch_to_tm_spec(formula=args.formula, space_group=args.space_group,
                                material_id=args.material_id, client=client, author=args.author)
    except MPError as exc:
        print(f"FAIL  import-mp: {exc}", file=sys.stderr)
        return 2
    if not docs:
        print("FAIL  import-mp: no MP material matched", file=sys.stderr)
        return 1

    if args.json:
        text = json.dumps(docs if len(docs) > 1 else docs[0], indent=2, ensure_ascii=False)
    else:
        text = "\n---\n".join(_to_yaml(d) for d in docs)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"WROTE {args.out} ({len(docs)} doc(s))")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
