"""Import OPTIMADE ``structures`` entries into TM-Spec documents.

OPTIMADE is a federated REST standard: many materials databases expose the
same ``/structures`` endpoint and the same JSON property names (the schema is
``elements`` / ``chemical_formula_*`` / ``lattice_vectors`` / ``species`` / ...).
That makes a single importer reusable across providers — Materials Project,
NOMAD, OQMD, Alexandria, etc.

Unlike a NOMAD *archive* entry (which carries method / XC / energies), an
OPTIMADE structures entry is **structure-level only**: it does not report the
relaxation status, the XC functional, the spin treatment, or any energy. The
importer is honest about that:

    * ``structure.geometry_origin`` is always ``"unknown"`` — OPTIMADE never
      tells us whether a geometry was relaxed, static, experimental or as-built.
    * ``calculation`` is a minimal ``{"method": "DFT"}`` stub (the schema makes
      ``calculation`` a required top-level block; OPTIMADE has nothing to fill
      it with, so we emit the smallest valid placeholder rather than fabricate
      an XC functional).
    * ``results`` is ``{"status": "PRELIMINARY", "paper_quotable": false}``
      (``SinglePointCalculation`` requires ``results`` but OPTIMADE has no
      energy to quote).

The field mapping follows ``docs/standards-alignment.md`` §2 (OPTIMADE):

    chemical_formula_descriptive / _reduced / _anonymous  -> structure.*
    chemical_formula_descriptive (or _reduced)            -> structure.formula
    lattice_vectors                                       -> structure.lattice_vectors_A
    dimension_types / nperiodic_dimensions                -> structure.pbc + dimension_types
    structure_features                                    -> sanity note (G06)
    id + provider                                         -> provenance.import_source

Architecture (mirrors ``importers.nomad``):

    import_optimade(elements, ...)            network glue → list[tm-spec docs]
    _parse_optimade_structures(json)          pure transform (mockable, offline)
    structure_to_tm_spec(entry, provider)     one OPTIMADE entry → one tm-spec doc

CLI (dispatched from ``tm_spec.cli``):

    tm-spec import-optimade --elements Fe S [--reduced-formula FeS2] \
        [--provider mp] [--page-limit 20] [--raw-filter '...'] \
        [--out FILE | --json] [--offline] [--merge BASE.tm.yaml]
    tm-spec import-optimade-batch --elements Fe S --out-dir DIR/ ...

``--merge BASE`` loads a (usually NOMAD-imported) TM-Spec doc and merges each
OPTIMADE hit into it via ``tm_spec.merge.merge_docs`` (fill-only, same-material
guarded) so the deep NOMAD method/results stay and the broad OPTIMADE structure
fields fill the holes — all locally, no manual editing.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import __version__ as TM_SPEC_VERSION

# Known OPTIMADE structures endpoints. The Materials Project endpoint is the
# default and has been smoke-tested; the others follow the same federated API.
PROVIDERS: dict[str, str] = {
    "mp":          "https://optimade.materialsproject.org/v1/structures",
    "nomad":       "https://nomad-lab.eu/prod/v1/optimade/v1/structures",
    "oqmd":        "https://oqmd.org/optimade/v1/structures",
    "alexandria":  "https://alexandria.icams.rub.de/pbe/v1/structures",
}
DEFAULT_PROVIDER = "mp"

# OPTIMADE archive label -> provenance.import_source.archive enum (schema 0.3
# allows nomad / materials_project / aflow / oqmd / jarvis / other).
_PROVIDER_TO_ARCHIVE: dict[str, str] = {
    "mp":         "materials_project",
    "nomad":      "nomad",
    "oqmd":       "oqmd",
    "alexandria": "other",
}

USER_AGENT = f"tm-spec/{TM_SPEC_VERSION} (+https://github.com/exopoiesis/tm-spec)"


class OptimadeError(RuntimeError):
    """Raised on HTTP / parse errors from an OPTIMADE endpoint."""


# ---------------------------------------------------------------------------
# Filter construction


def build_filter(
    elements: list[str] | None,
    reduced_formula: str | None = None,
    raw_filter: str | None = None,
) -> str:
    """Build an OPTIMADE ``filter`` string.

    ``raw_filter`` (if given) is used verbatim and overrides the rest.
    Otherwise a ``chemical_formula_reduced`` equality is preferred when a
    reduced formula is supplied, else an ``elements HAS ALL`` clause.
    """
    if raw_filter:
        return raw_filter
    if reduced_formula:
        return f'chemical_formula_reduced="{reduced_formula}"'
    if elements:
        joined = ",".join(f'"{e}"' for e in elements)
        return f"elements HAS ALL {joined}"
    raise OptimadeError("need elements, reduced_formula or raw_filter to build an OPTIMADE filter")


# ---------------------------------------------------------------------------
# HTTP client (httpx if available, else stdlib urllib — keeps the package
# dependency-light: pyyaml + jsonschema only).


def _http_get_json(url: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
    """GET ``url?params`` and return parsed JSON. Prefers httpx, falls back to urllib."""
    try:
        import httpx  # type: ignore

        try:
            resp = httpx.get(
                url,
                params=params,
                timeout=timeout,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:  # network / status / decode
            raise OptimadeError(f"OPTIMADE GET {url} -> {exc}") from exc

    except ImportError:
        full = url + "?" + urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(
            full,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = r.read()
        except urllib.error.HTTPError as exc:
            raise OptimadeError(f"OPTIMADE GET {url} -> HTTP {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise OptimadeError(f"OPTIMADE GET {url} -> network error: {exc}") from exc
        if not payload:
            return {}
        try:
            return json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise OptimadeError(f"OPTIMADE GET {url} -> invalid JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# OPTIMADE entry -> TM-Spec mapping


def _slug(s: str) -> str:
    """Make a string safe for the TM-Spec ``id`` pattern (mirror nomad._slug)."""
    out = []
    for ch in s:
        out.append(ch if (ch.isalnum() or ch in "_.+-") else "_")
    flat = "".join(out)
    while "__" in flat:
        flat = flat.replace("__", "_")
    return flat.strip("_") or "entry"


def _pbc_from_optimade(attrs: dict[str, Any]) -> tuple[list[bool] | None, list[int] | None]:
    """Derive ``(pbc, dimension_types)`` from an OPTIMADE attributes block.

    Prefers ``dimension_types`` (``[0|1, 0|1, 0|1]``); falls back to
    ``nperiodic_dimensions`` (an int 0..3, expanded leading-True). Returns
    ``(None, None)`` when neither is present — the caller then omits pbc.
    """
    dt = attrs.get("dimension_types")
    if isinstance(dt, list) and len(dt) == 3 and all(v in (0, 1) for v in dt):
        return [bool(v) for v in dt], [int(v) for v in dt]
    nper = attrs.get("nperiodic_dimensions")
    if isinstance(nper, int) and 0 <= nper <= 3:
        dim = [1] * nper + [0] * (3 - nper)
        return [bool(v) for v in dim], dim
    return None, None


def _structure_block(attrs: dict[str, Any]) -> dict[str, Any]:
    """Build TM-Spec ``structure`` block from OPTIMADE structures attributes."""
    out: dict[str, Any] = {}

    descriptive = attrs.get("chemical_formula_descriptive")
    reduced = attrs.get("chemical_formula_reduced")
    anonymous = attrs.get("chemical_formula_anonymous")

    # structure.formula: prefer the descriptive (human) formula, else reduced.
    formula = descriptive or reduced
    if formula:
        out["formula"] = formula
    if descriptive:
        out["chemical_formula_descriptive"] = descriptive
    if reduced:
        out["chemical_formula_reduced"] = reduced
    if anonymous:
        out["chemical_formula_anonymous"] = anonymous

    lattice = attrs.get("lattice_vectors")
    if (
        isinstance(lattice, list)
        and len(lattice) == 3
        and all(isinstance(v, list) and len(v) == 3 for v in lattice)
        and all(isinstance(x, (int, float)) for v in lattice for x in v)
    ):
        out["lattice_vectors_A"] = [[float(x) for x in v] for v in lattice]

    pbc, dim = _pbc_from_optimade(attrs)
    if pbc is not None:
        out["pbc"] = pbc
    if dim is not None:
        out["dimension_types"] = dim

    # OPTIMADE never reports relaxation status -> honest "unknown".
    out["geometry_origin"] = "unknown"

    return out or {"formula": "Unknown", "geometry_origin": "unknown"}


def _entry_date(attrs: dict[str, Any]) -> str:
    """ISO date for the entry. Fallback: today (UTC)."""
    raw = attrs.get("last_modified")
    if isinstance(raw, str) and len(raw) >= 10:
        return raw[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def structure_to_tm_spec(
    entry: dict[str, Any],
    *,
    provider: str = DEFAULT_PROVIDER,
    base_url: str | None = None,
    doc_id: str | None = None,
    author: str = "import@optimade",
) -> dict[str, Any]:
    """Pure transformation: one OPTIMADE ``structures`` entry -> TM-Spec doc.

    ``entry`` is a single object from the OPTIMADE ``data`` array
    (``{"id": ..., "type": "structures", "attributes": {...}}``). No network.

    The result is always valid against schema 0.3 for ``SinglePointCalculation``
    if the entry has the expected OPTIMADE shape: ``structure`` (with at least
    a formula), a minimal ``calculation``, an empty ``sanity`` (plus one note
    gate), a minimal ``results``, and ``provenance.import_source``.
    """
    if not isinstance(entry, dict):
        raise OptimadeError(f"entry must be a dict, got {type(entry).__name__}")

    attrs = entry.get("attributes")
    if not isinstance(attrs, dict):
        attrs = {}

    entry_id = str(entry.get("id") or attrs.get("id") or "unknown")
    date = _entry_date(attrs)
    if doc_id is None:
        doc_id = f"tm.optimade_{_slug(provider)}.{_slug(entry_id)}.{date}"

    structure = _structure_block(attrs)

    # OPTIMADE structure_features (disorder / implicit_atoms / ...) surfaced as a
    # non-blocking note on the G06 gate. Empty list means "ordered, fully described".
    features = attrs.get("structure_features")
    if isinstance(features, list):
        feat_note = (
            "OPTIMADE structure_features: " + ", ".join(str(f) for f in features)
            if features
            else "OPTIMADE structure_features: [] (ordered, fully described)"
        )
    else:
        feat_note = "OPTIMADE structure_features not reported"

    sanity_gates: list[dict[str, Any]] = [
        {
            "id":   "G06_ascii_safe",
            "rule": "ASCII-only doc body",
            "note": feat_note,
            "pass": "skip",
        },
        # OPTIMADE has no relaxation status -> geometry_origin is unknown.
        {
            "id":       "G09_geometry_origin",
            "rule":     "geometry_origin is dft_relaxed/dft_static, not an MLIP geometry",
            "observed": "unknown",
            "pass":     "skip",
        },
    ]

    archive = _PROVIDER_TO_ARCHIVE.get(provider, "other")
    endpoint_url = base_url or PROVIDERS.get(provider, "")
    entry_url = f"{endpoint_url.rstrip('/')}/{urllib.parse.quote(entry_id)}" if endpoint_url else ""

    import_source: dict[str, Any] = {
        "archive":     archive,
        "entry_id":    entry_id,
        "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "importer":    f"tm-spec import-optimade@{TM_SPEC_VERSION}",
        "raw_keys": [
            "attributes.chemical_formula_descriptive",
            "attributes.chemical_formula_reduced",
            "attributes.chemical_formula_anonymous",
            "attributes.lattice_vectors",
            "attributes.dimension_types",
            "attributes.structure_features",
            "id",
        ],
    }
    if entry_url:
        import_source["url"] = entry_url

    provenance: dict[str, Any] = {
        "date":          date,
        "author":        author,
        "import_source": import_source,
        "compute":       {"host": f"optimade:{provider}", "cost_usd": 0.0},
    }

    doc: dict[str, Any] = {
        "spec":        "tm-spec/0.3",
        "kind":        "SinglePointCalculation",
        "id":          doc_id,
        "schema_url":  "https://exopoiesis.github.io/tm-spec/0.3.json",
        "structure":   structure,
        # OPTIMADE carries no method/XC/energy. Emit the smallest valid
        # calculation stub (method is the only required field) rather than
        # fabricate an XC functional.
        "calculation": {"method": "DFT"},
        "results": {
            "status":         "PRELIMINARY",
            "paper_quotable": False,
            "notes": (
                "Imported from OPTIMADE (structure-level only); no method/XC/energy "
                "reported. Run a calculation + sanity_fill before quoting."
            ),
        },
        "sanity":     sanity_gates,
        "provenance": provenance,
    }
    return doc


def _parse_optimade_structures(
    payload: dict[str, Any],
    *,
    provider: str = DEFAULT_PROVIDER,
    base_url: str | None = None,
    author: str = "import@optimade",
) -> list[dict[str, Any]]:
    """Pure transform: an OPTIMADE structures response -> list of TM-Spec docs.

    Isolated so tests can feed a cached/mocked JSON response without network.
    Accepts the standard ``{"data": [ {entry}, ... ], "meta": {...}}`` shape;
    a bare list of entries is also tolerated.
    """
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        data = payload.get("data")
        rows = data if isinstance(data, list) else []
    else:
        raise OptimadeError(f"unexpected OPTIMADE payload type: {type(payload).__name__}")

    out: list[dict[str, Any]] = []
    for entry in rows:
        if isinstance(entry, dict):
            out.append(
                structure_to_tm_spec(
                    entry, provider=provider, base_url=base_url, author=author
                )
            )
    return out


# ---------------------------------------------------------------------------
# Network glue


def import_optimade(
    elements: list[str] | None,
    reduced_formula: str | None = None,
    provider: str = DEFAULT_PROVIDER,
    page_limit: int = 20,
    raw_filter: str | None = None,
    timeout: float = 15.0,
    live: bool = True,
    base_url: str | None = None,
    author: str = "import@optimade",
) -> list[dict[str, Any]]:
    """Query an OPTIMADE provider for structures and return TM-Spec docs.

    Parameters
    ----------
    elements:
        Element symbols for an ``elements HAS ALL "Fe","S"`` filter.
    reduced_formula:
        If given, query ``chemical_formula_reduced="<formula>"`` instead.
    provider:
        Key into :data:`PROVIDERS` (``"mp"`` default) or ignored when
        ``base_url`` is set.
    page_limit:
        OPTIMADE ``page_limit`` query parameter (max entries per page).
    raw_filter:
        Verbatim OPTIMADE filter; overrides ``elements`` / ``reduced_formula``.
    timeout:
        Per-request timeout (seconds).
    live:
        When ``False``, no network call is made and an empty list is returned
        (offline mode — use ``_parse_optimade_structures`` on a cached payload).
    base_url:
        Override the endpoint URL (for staging / unknown providers).
    author:
        ``provenance.author`` email. Default ``import@optimade`` (synthetic).

    Returns
    -------
    list[dict]
        One TM-Spec ``SinglePointCalculation`` doc per OPTIMADE structure.
    """
    if not live:
        return []

    url = base_url or PROVIDERS.get(provider)
    if not url:
        raise OptimadeError(
            f"unknown provider {provider!r}; known: {sorted(PROVIDERS)} (or pass base_url)"
        )

    filt = build_filter(elements, reduced_formula, raw_filter)
    params = {"filter": filt, "page_limit": int(page_limit)}
    payload = _http_get_json(url, params, timeout)
    return _parse_optimade_structures(
        payload, provider=provider, base_url=url, author=author
    )


# ---------------------------------------------------------------------------
# YAML emission (mirror importers.nomad)


def _to_yaml(doc: dict[str, Any]) -> str:
    import yaml  # local import: yaml is a runtime dep already

    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)


def _write_doc(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_yaml(doc), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI dispatch


def _add_query_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--elements",
        nargs="+",
        help="Element symbols, e.g. --elements Fe S (elements HAS ALL ...).",
    )
    parser.add_argument(
        "--reduced-formula",
        default=None,
        help='Query chemical_formula_reduced="FeS2" instead of elements.',
    )
    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        help=f"OPTIMADE provider key (default: {DEFAULT_PROVIDER}). Known: {sorted(PROVIDERS)}.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the OPTIMADE structures endpoint URL (for staging/unknown providers).",
    )
    parser.add_argument("--page-limit", type=int, default=20, help="OPTIMADE page_limit.")
    parser.add_argument(
        "--raw-filter",
        default=None,
        help="Verbatim OPTIMADE filter (overrides --elements / --reduced-formula).",
    )
    parser.add_argument(
        "--author",
        default="import@optimade",
        help="Email for provenance.author. Default: import@optimade.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not hit the network (returns nothing; for smoke/CI).",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout (s).")


def main(argv: list[str] | None = None) -> int:
    """``tm-spec import-optimade`` — query one provider, emit (or merge) docs."""
    parser = argparse.ArgumentParser(
        prog="tm-spec import-optimade",
        description="Import OPTIMADE structures into TM-Spec docs (optionally merged into a base).",
    )
    _add_query_args(parser)
    parser.add_argument("--out", "-o", type=Path, help="Output YAML path. Default: stdout.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of YAML (one doc, or a JSON array if multiple).",
    )
    parser.add_argument(
        "--merge",
        type=Path,
        default=None,
        help=(
            "Path to a TM-Spec doc (usually a NOMAD import) to use as the merge base. "
            "Each OPTIMADE hit is merged into it (fill-only, same-material guarded)."
        ),
    )
    parser.add_argument(
        "--allow-material-mismatch",
        action="store_true",
        help="With --merge: warn instead of erroring on a formula mismatch.",
    )
    args = parser.parse_args(argv)

    try:
        docs = import_optimade(
            elements=args.elements,
            reduced_formula=args.reduced_formula,
            provider=args.provider,
            page_limit=args.page_limit,
            raw_filter=args.raw_filter,
            timeout=args.timeout,
            live=not args.offline,
            base_url=args.base_url,
            author=args.author,
        )
    except OptimadeError as exc:
        print(f"FAIL  import-optimade: {exc}", file=sys.stderr)
        return 2

    if not docs:
        msg = "no structures returned" if not args.offline else "offline mode: nothing fetched"
        print(f"WARN  import-optimade: {msg}", file=sys.stderr)
        return 0

    # --merge: fold OPTIMADE hits into a local base doc (NOMAD depth + OPTIMADE width).
    if args.merge is not None:
        from ..merge import MergeError, load_first_doc, merge_docs, pick_same_material

        try:
            base = load_first_doc(args.merge)
        except Exception as exc:
            print(f"FAIL  import-optimade --merge: cannot load base {args.merge}: {exc}",
                  file=sys.stderr)
            return 2

        overlay, mismatch_warns = pick_same_material(base, docs)
        for w in mismatch_warns:
            print(f"WARN  {w}", file=sys.stderr)
        try:
            merged, warns = merge_docs(
                base, overlay, strict_material=not args.allow_material_mismatch
            )
        except MergeError as exc:
            print(f"FAIL  import-optimade --merge: {exc}", file=sys.stderr)
            return 2
        for w in warns:
            print(f"WARN  {w}", file=sys.stderr)
        docs = [merged]

    if args.out:
        if len(docs) == 1:
            _write_doc(docs[0], args.out)
            print(f"WROTE {args.out} (kind={docs[0]['kind']}, id={docs[0]['id']})")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            if args.json:
                args.out.write_text(json.dumps(docs, indent=2), encoding="utf-8")
            else:
                args.out.write_text(
                    "".join("---\n" + _to_yaml(d) for d in docs), encoding="utf-8"
                )
            print(f"WROTE {args.out} ({len(docs)} docs)")
        return 0

    if args.json:
        payload = docs[0] if len(docs) == 1 else docs
        print(json.dumps(payload, indent=2))
    else:
        for d in docs:
            print(_to_yaml(d), end="")
            if len(docs) > 1:
                print("---")
    return 0


def main_batch(argv: list[str] | None = None) -> int:
    """``tm-spec import-optimade-batch`` — write one YAML per OPTIMADE hit."""
    parser = argparse.ArgumentParser(
        prog="tm-spec import-optimade-batch",
        description="Query OPTIMADE and write one <id>.tm.yaml per matching structure.",
    )
    _add_query_args(parser)
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Directory to write per-structure YAML into.",
    )
    args = parser.parse_args(argv)

    try:
        docs = import_optimade(
            elements=args.elements,
            reduced_formula=args.reduced_formula,
            provider=args.provider,
            page_limit=args.page_limit,
            raw_filter=args.raw_filter,
            timeout=args.timeout,
            live=not args.offline,
            base_url=args.base_url,
            author=args.author,
        )
    except OptimadeError as exc:
        print(f"FAIL  import-optimade-batch: {exc}", file=sys.stderr)
        return 2

    n_ok = 0
    for doc in docs:
        eid = (doc.get("provenance", {}).get("import_source", {}) or {}).get("entry_id", "entry")
        out_path = args.out_dir / f"{_slug(str(eid))}.tm.yaml"
        _write_doc(doc, out_path)
        print(f"WROTE {out_path}  [{doc['kind']}]")
        n_ok += 1

    print(f"Summary: {n_ok} written.", file=sys.stderr)
    return 0
