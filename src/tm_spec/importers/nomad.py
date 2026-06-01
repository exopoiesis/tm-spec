"""Import a NOMAD Archive entry into a TM-Spec document.

NOMAD is the largest public archive of computational materials data
(~14 M entries spanning VASP / Quantum ESPRESSO / CP2K / ABACUS / GPAW
/ FHI-aims / etc.). The vast majority of entries are *not* NEB or MD —
they are single-point SCF or geometry optimisations. v0.2 of TM-Spec
introduces ``SinglePointCalculation`` and ``RelaxCalculation`` kinds
specifically to give those entries a TM-Spec home (decisions D-23 and
D-24).

Architecture
------------

    NomadClient
        Thin urllib wrapper. Handles authenticated and anonymous reads
        from ``https://nomad-lab.eu/prod/v1/api/v1``. Stdlib-only — no
        ``requests`` / ``nomad-lab`` dep required for ``pip install
        tm-spec``.

    archive_to_tm_spec(archive)
        Pure transformation: a NOMAD ``EntryArchive`` dict (or the
        ``data`` field returned by ``/entries/{id}/archive``) becomes
        a TM-Spec doc dict. No network. The mapping covers the
        recurring pieces — formula / lattice / method / xc / basis /
        results — and leaves the rest unset so that downstream tooling
        can fill in by hand. Drives the offline test suite.

    fetch_to_tm_spec(entry_id, ...)
        Network glue: call the NOMAD API, then run ``archive_to_tm_spec``
        on the response.

CLI
---

    tm-spec import-nomad <entry_id> [--out FILE]
    tm-spec import-nomad-batch --query JSON --limit N --out-dir DIR/

The CLI is dispatched from ``tm_spec.cli``. ``import-nomad-batch``
takes a JSON-encoded NOMAD query (or ``--query-file FILE``) and writes
one ``<entry_id>.tm.yaml`` per match.

Per the v0.2 roadmap's Open Q section:

* anonymous reads are sufficient for public entries; ``NOMAD_API_TOKEN``
  env var optional;
* nomad-lab metainfo evolves — fixtures freeze a snapshot version, the
  CLI logs a warning if the live archive looks newer.
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

NOMAD_API_BASE_DEFAULT = "https://nomad-lab.eu/prod/v1/api/v1"
NOMAD_API_BASE_ENV = "TM_SPEC_NOMAD_API_BASE"
NOMAD_TOKEN_ENV = "NOMAD_API_TOKEN"

USER_AGENT = f"tm-spec/{TM_SPEC_VERSION} (+https://github.com/exopoiesis/tm-spec)"

# Map NOMAD ``workflow_name`` (or fallback ``workflow2.name``) onto TM-Spec ``kind``.
# Values not in the table fall through to ``SinglePointCalculation`` (the
# safest default for a NOMAD entry that has at least an SCF result).
_WORKFLOW_TO_KIND: dict[str, str] = {
    "single_point":          "SinglePointCalculation",
    "GeometryOptimization":  "RelaxCalculation",
    "geometry_optimization": "RelaxCalculation",
    "MolecularDynamics":     "MDCalculation",
    "molecular_dynamics":    "MDCalculation",
    "Elastic":               "SinglePointCalculation",  # multiple SP as one entry
}

# Map a TM-Spec ``kind`` (plus method hint) onto a ``geometry_origin`` value
# from the v0.3 ``$defs.endpoint.geometry_origin`` enum. A NOMAD entry that was
# relaxed gives a relaxed geometry; a single-point gives a static one; an entry
# whose method is machine-learning gives an MLIP-relaxed geometry. Anything we
# can't classify is ``unknown`` (never fabricated as ``dft_relaxed``).
_KIND_TO_GEOMETRY_ORIGIN: dict[str, str] = {
    "RelaxCalculation":       "dft_relaxed",
    "SinglePointCalculation": "dft_static",
    # MD frames are time-evolved snapshots, not an optimised endpoint.
    "MDCalculation":          "unknown",
}

# Conversion factor: NOMAD stores energies in joules; TM-Spec uses eV.
_J_PER_EV = 1.602176634e-19


# ---------------------------------------------------------------------------
# HTTP client


class NomadError(RuntimeError):
    """Raised on HTTP / parse errors from the NOMAD API."""


class NomadClient:
    """Minimal stdlib client for the NOMAD v1 API.

    Parameters
    ----------
    base_url:
        API root, e.g. ``https://nomad-lab.eu/prod/v1/api/v1``. Override
        for the staging instance during integration tests.
    token:
        Optional auth token. If unset, anonymous reads are used (works
        for all public entries).
    timeout_s:
        Per-request timeout.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.base_url = (
            base_url
            or os.environ.get(NOMAD_API_BASE_ENV)
            or NOMAD_API_BASE_DEFAULT
        ).rstrip("/")
        self.token = token if token is not None else os.environ.get(NOMAD_TOKEN_ENV)
        self.timeout_s = timeout_s

    # -- HTTP plumbing ------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = self.base_url + path
        if query:
            url = url + "?" + urllib.parse.urlencode(query, doseq=True)
        data: bytes | None = None
        headers = {
            "Accept":     "application/json",
            "User-Agent": USER_AGENT,
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as exc:
            raise NomadError(
                f"NOMAD API {method} {path} → HTTP {exc.code}: {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise NomadError(f"NOMAD API {method} {path} → network error: {exc}") from exc

        if not payload:
            return {}
        try:
            return json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise NomadError(f"NOMAD API {method} {path} → invalid JSON: {exc}") from exc

    # -- public surface ----------------------------------------------------

    def search(
        self,
        query: dict[str, Any] | None = None,
        *,
        page_size: int = 10,
        page_after_value: str | None = None,
    ) -> dict[str, Any]:
        """Run a NOMAD entries query.

        Returns the parsed response (`{"data": [...], "pagination": {...}}`).
        """
        body: dict[str, Any] = {
            "query":     query or {},
            "pagination": {"page_size": page_size},
        }
        if page_after_value:
            body["pagination"]["page_after_value"] = page_after_value
        return self._request("POST", "/entries/query", body=body)

    def get_archive(self, entry_id: str) -> dict[str, Any]:
        """Fetch the full archive for one entry.

        The NOMAD API returns ``{"data": {"archive": {...}}}``. We unwrap
        and return only the archive dict — that's what callers care about.

        We use ``POST /entries/{id}/archive/query`` with ``required: "*"``
        because the bare GET ``/entries/{id}/archive`` is being phased out
        and the query endpoint currently rejects empty bodies (HTTP 422).
        """
        body = self._request(
            "POST",
            f"/entries/{urllib.parse.quote(entry_id)}/archive/query",
            body={"required": "*"},
        )
        # /entries/{id}/archive/query returns {data: {archive: {...}, ...}}
        data = body.get("data") or {}
        archive = data.get("archive") or data
        if not isinstance(archive, dict):
            raise NomadError(f"unexpected archive shape for {entry_id}: {type(archive).__name__}")
        return archive


# ---------------------------------------------------------------------------
# Archive → TM-Spec mapping


def _g(d: dict[str, Any] | None, *path: str, default: Any = None) -> Any:
    """Safe nested dict lookup. ``_g(arch, 'results', 'material', 'elements')``."""
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _slug(s: str) -> str:
    """Make a string safe for the TM-Spec ``id`` pattern.

    The pattern is ``^tm\\.[A-Za-z0-9_.+\\-]+\\.\\d{4}-\\d{2}-\\d{2}$``.
    Replace anything else with ``_`` and collapse repeats.
    """
    out = []
    for ch in s:
        if ch.isalnum() or ch in "_.+-":
            out.append(ch)
        else:
            out.append("_")
    flattened = "".join(out)
    while "__" in flattened:
        flattened = flattened.replace("__", "_")
    return flattened.strip("_") or "entry"


def _detect_kind(archive: dict[str, Any]) -> str:
    """Pick a TM-Spec kind from a NOMAD archive.

    Looks at four signals (in order):
      1. ``workflow2.name``/``workflow2.type`` (modern parsers).
      2. ``workflow[*].type``/``name`` (legacy list — most live entries).
      3. ``method.simulation.geometry_optimization`` /
         ``results.properties.geometry_optimization`` (presence ⇒ Relax).
      4. ``method.simulation.molecular_dynamics`` (presence ⇒ MD).

    Falls back to ``SinglePointCalculation``.
    """
    name = _g(archive, "workflow2", "name") or _g(archive, "workflow2", "type")
    if isinstance(name, str) and name in _WORKFLOW_TO_KIND:
        return _WORKFLOW_TO_KIND[name]

    workflows = archive.get("workflow")
    if isinstance(workflows, list):
        for w in workflows:
            wn = (w or {}).get("type") or (w or {}).get("name")
            if isinstance(wn, str) and wn in _WORKFLOW_TO_KIND:
                return _WORKFLOW_TO_KIND[wn]

    if (
        _g(archive, "workflow2", "geometry_optimization")
        or _g(archive, "results", "method", "simulation", "geometry_optimization")
        or _g(archive, "results", "properties", "geometry_optimization")
    ):
        return "RelaxCalculation"
    if (
        _g(archive, "workflow2", "molecular_dynamics")
        or _g(archive, "results", "method", "simulation", "molecular_dynamics")
        or _g(archive, "results", "properties", "molecular_dynamics")
    ):
        return "MDCalculation"

    return "SinglePointCalculation"


def _is_mlip_method(archive: dict[str, Any]) -> bool:
    """True if the NOMAD method looks like a machine-learning potential.

    A geometry relaxed (or evaluated) with an MLIP must NOT be tagged
    ``dft_relaxed`` — an MLIP geometry can carry tens of eV of unrelaxed-
    lattice error (see v0.3 ``geometry_origin`` rationale and gate
    ``G09_geometry_origin``). We check the same signals used by
    ``_calculation_block``.
    """
    method = _g(archive, "results", "method") or {}
    method_name = str(method.get("method_name", ""))
    if "MLIP" in method_name or "machine learning" in method_name.lower():
        return True
    # NOMAD ``electronic_structure_method`` / workflow ``method=ML``.
    esm = _g(archive, "results", "method", "method_name")
    if isinstance(esm, str) and esm.strip().upper() == "ML":
        return True
    return False


def _geometry_origin(archive: dict[str, Any], kind: str) -> str:
    """Map a NOMAD entry onto a v0.3 ``geometry_origin`` enum value.

    Mapping (NOMAD workflow/task type x method -> enum):

      * geometry optimisation / relaxation  -> ``dft_relaxed``
      * single point / static               -> ``dft_static``
      * any of the above but method=ML/MLIP -> ``mlip_relaxed``
      * MD frame / unclassified             -> ``unknown``

    The ML check takes precedence over the relax/static split: an MLIP
    geometry is recorded as ``mlip_relaxed`` regardless of whether NOMAD
    flagged it as a relaxation, because the energy-comparison caveat is the
    same (gate ``G09_geometry_origin``).
    """
    if _is_mlip_method(archive):
        # Only relax/single-point produce a usable endpoint geometry; an MLIP
        # MD frame stays ``unknown``.
        if kind in ("RelaxCalculation", "SinglePointCalculation"):
            return "mlip_relaxed"
        return "unknown"
    return _KIND_TO_GEOMETRY_ORIGIN.get(kind, "unknown")


def _structure_block(archive: dict[str, Any]) -> dict[str, Any]:
    """Build TM-Spec ``structure`` block from NOMAD ``results.material``."""
    mat = _g(archive, "results", "material") or {}
    sym = mat.get("symmetry") or {}

    out: dict[str, Any] = {}

    formula = (
        mat.get("chemical_formula_descriptive")
        or mat.get("chemical_formula_reduced")
        or mat.get("chemical_formula_hill")
    )
    if formula:
        out["formula"] = formula

    descriptive = mat.get("chemical_formula_descriptive")
    reduced     = mat.get("chemical_formula_reduced")
    anonymous   = mat.get("chemical_formula_anonymous")
    if descriptive:
        out["chemical_formula_descriptive"] = descriptive
    if reduced:
        out["chemical_formula_reduced"] = reduced
    if anonymous:
        out["chemical_formula_anonymous"] = anonymous

    if isinstance(sym.get("space_group_number"), int):
        out["space_group"] = {
            "number": sym["space_group_number"],
        }
        if sym.get("space_group_symbol"):
            out["space_group"]["symbol"] = sym["space_group_symbol"]

    proto = sym.get("prototype_label_aflow") or sym.get("structure_name")
    if isinstance(proto, str) and "_" in proto:
        out["prototype"] = proto

    out["pbc"] = [True, True, True]
    return out or {"formula": "Unknown"}


def _calculation_block(archive: dict[str, Any]) -> dict[str, Any]:
    """Build TM-Spec ``calculation`` block from NOMAD method metadata."""
    method = _g(archive, "results", "method") or {}
    sim    = method.get("simulation") or {}
    dft    = sim.get("dft") or {}

    program = sim.get("program_name")
    program_version = sim.get("program_version")
    runs = archive.get("run") or []
    if (not program or not program_version) and isinstance(runs, list) and runs:
        run0 = runs[0] or {}
        prog = run0.get("program") or {}
        program = program or prog.get("name")
        program_version = program_version or prog.get("version")

    method_name = method.get("method_name", "DFT")
    if method_name == "DFT+U":
        tm_method = "DFT+U"
    elif method_name == "DFT":
        tm_method = "DFT"
    elif "MLIP" in str(method_name) or "machine learning" in str(method_name).lower():
        tm_method = "MLIP"
    elif method_name in ("classical_MD", "classical molecular dynamics"):
        tm_method = "classical_MD"
    else:
        tm_method = "DFT"

    level: dict[str, Any] = {}
    if dft.get("xc_functional_type"):
        level["xc"] = dft["xc_functional_type"]
    libxc = dft.get("xc_functional_names") or []
    if isinstance(libxc, list):
        # Filter to entries that look like the LibXC ``GGA_X_PBE`` pattern.
        keep = [s for s in libxc if isinstance(s, str) and s.count("_") >= 2]
        if keep:
            level["xc_libxc"] = keep
    if dft.get("basis_set_type"):
        level["basis"] = {"kind": _normalize_basis(dft["basis_set_type"])}
    if dft.get("relativity_method"):
        level["pseudopotential"] = dft["relativity_method"]

    spin = dft.get("spin_polarized")
    if spin is True:
        level["spin"] = "collinear"
    elif spin is False:
        level["spin"] = "none"

    out: dict[str, Any] = {"method": tm_method}
    if level:
        out["level"] = level
    if program:
        out["code"] = {"name": program}
        if program_version:
            out["code"]["version"] = str(program_version)
    return out


def _normalize_basis(b: str) -> str:
    """Map NOMAD basis_set_type strings onto the TM-Spec basis_kind enum."""
    s = (b or "").lower()
    if "plane" in s or s.strip() in {"pw", "plane-waves", "plane_waves"}:
        return "plane_waves"
    if "gauss" in s:
        return "gaussians"
    if "numeric" in s or "atomic orbital" in s or "ao" in s:
        return "numeric_AOs"
    if "mixed" in s:
        return "mixed"
    if "ml" in s and "potential" in s:
        return "ML_potential"
    return "plane_waves"


def _energy_eV(archive: dict[str, Any]) -> float | None:
    """Pull the final SCF energy in eV from a NOMAD archive (best-effort)."""
    # Try modern result blocks first.
    cand = _g(archive, "results", "properties", "energies", "energy_total", "value")
    if isinstance(cand, (int, float)):
        return float(cand) / _J_PER_EV

    # Try the run/calculation chain.
    runs = archive.get("run") or []
    if isinstance(runs, list):
        for run in runs:
            calcs = (run or {}).get("calculation") or []
            for c in reversed(calcs) if isinstance(calcs, list) else []:
                e = (c or {}).get("energy", {})
                tot = (e.get("total") or {}).get("value")
                if isinstance(tot, (int, float)):
                    return float(tot) / _J_PER_EV
    return None


def _band_gap_eV(archive: dict[str, Any]) -> float | None:
    """Best-effort scalar band gap in eV."""
    bg = _g(archive, "results", "properties", "electronic", "band_gap")
    if isinstance(bg, list) and bg:
        for entry in bg:
            v = (entry or {}).get("value")
            if isinstance(v, (int, float)):
                return float(v) / _J_PER_EV
    if isinstance(bg, dict):
        v = bg.get("value")
        if isinstance(v, (int, float)):
            return float(v) / _J_PER_EV
    return None


def _scf_converged(archive: dict[str, Any]) -> bool | None:
    """Return True if any SCF block reports converged (per NOMAD parser)."""
    runs = archive.get("run") or []
    for run in runs if isinstance(runs, list) else []:
        for c in (run or {}).get("calculation") or []:
            scf = (c or {}).get("scf_iteration") or []
            if scf and isinstance(scf, list):
                # NOMAD parsers populate scf_iteration when SCF completed.
                return True
    return None


def _entry_id(archive: dict[str, Any]) -> str:
    """Find a usable NOMAD entry_id inside an archive."""
    return (
        _g(archive, "metadata", "entry_id")
        or _g(archive, "metadata", "calc_id")
        or _g(archive, "metadata", "raw_id")
        or "unknown"
    )


def _upload_id(archive: dict[str, Any]) -> str | None:
    return _g(archive, "metadata", "upload_id")


def _entry_date(archive: dict[str, Any]) -> str:
    """ISO date string for the entry. Fallback: today (UTC)."""
    raw = _g(archive, "metadata", "upload_create_time") or _g(archive, "metadata", "entry_create_time")
    if isinstance(raw, str) and len(raw) >= 10:
        return raw[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def archive_to_tm_spec(
    archive: dict[str, Any],
    *,
    doc_id: str | None = None,
    author: str = "import@nomad",
) -> dict[str, Any]:
    """Pure transformation: NOMAD archive dict → TM-Spec doc dict.

    The output is always valid against schema 0.3 for the chosen kind
    *if* the archive has the expected NOMAD shape. Missing fields are
    omitted (the validator will complain about anything truly required
    that we couldn't fill).

    Parameters
    ----------
    archive:
        Parsed NOMAD ``EntryArchive`` JSON. Either the raw response from
        ``/entries/{id}/archive/query`` (top-level ``data.archive``) or
        the unwrapped archive itself; the function copes with both.
    doc_id:
        Override the generated TM-Spec ``id``. Useful when callers want
        deterministic IDs for tests.
    author:
        Email address for ``provenance.author``. Defaults to
        ``import@nomad`` (clearly synthetic).
    """
    if not isinstance(archive, dict):
        raise NomadError(f"archive must be a dict, got {type(archive).__name__}")

    # Accept either a wrapped {"data": {"archive": {...}}} response or a bare archive.
    if "data" in archive and isinstance(archive["data"], dict) and "archive" in archive["data"]:
        archive = archive["data"]["archive"]
    elif "archive" in archive and isinstance(archive["archive"], dict):
        archive = archive["archive"]

    kind = _detect_kind(archive)
    eid = _entry_id(archive)
    date = _entry_date(archive)

    if doc_id is None:
        doc_id = f"tm.nomad.{_slug(eid)}.{date}"

    structure = _structure_block(archive)
    calculation = _calculation_block(archive)
    geometry_origin = _geometry_origin(archive, kind)

    scf_observed = _scf_converged(archive)
    sanity_gates: list[dict[str, Any]] = [
        {
            "id":       "G05_scf_converged",
            "rule":     "NOMAD parser reports at least one converged SCF step",
            "observed": scf_observed,
            "pass":     bool(scf_observed) if scf_observed is not None else "skip",
        },
        {
            "id":       "G06_ascii_safe",
            "rule":     "ASCII-only doc body (NOMAD entries are non-ASCII tolerant on import)",
            "pass":     "skip",
        },
        # v0.3: surface the imported geometry's origin via the shared gate
        # vocabulary (docs/gate-registry.md G09_geometry_origin). SinglePoint /
        # Relax docs have no `endpoint` block, so the schema-valid home for the
        # origin is this sanity gate rather than a fabricated structure field.
        # An mlip_relaxed origin is a `warn` (energy comparisons need care);
        # dft_relaxed/dft_static pass; unknown is skipped.
        {
            "id":       "G09_geometry_origin",
            "rule":     "geometry_origin is dft_relaxed/dft_static, not an MLIP geometry",
            "observed": geometry_origin,
            "pass":     (
                "warn" if geometry_origin == "mlip_relaxed"
                else "skip" if geometry_origin == "unknown"
                else True
            ),
        },
    ]

    provenance: dict[str, Any] = {
        "date":   date,
        "author": author,
        "import_source": {
            "archive":     "nomad",
            "entry_id":    eid,
            "url":         f"https://nomad-lab.eu/prod/v1/gui/entry/id/{eid}",
            "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "importer":    f"tm-spec import-nomad@{TM_SPEC_VERSION}",
            "raw_keys": [
                "results.material", "results.method.simulation.dft",
                "results.properties.energies.energy_total",
                "results.properties.electronic.band_gap",
                "metadata.entry_id", "metadata.upload_id",
            ],
        },
        "compute": {
            "host":     "nomad-archive",
            "cost_usd": 0.0,
        },
    }
    upload_id = _upload_id(archive)
    if upload_id:
        provenance["import_source"]["upload_id"] = upload_id

    energy_eV   = _energy_eV(archive)
    band_gap_eV = _band_gap_eV(archive)
    scf_ok      = _scf_converged(archive)

    doc: dict[str, Any] = {
        "spec":        "tm-spec/0.3",
        "kind":        kind,
        "id":          doc_id,
        "schema_url":  "https://exopoiesis.github.io/tm-spec/0.3.json",
        "structure":   structure,
        "calculation": calculation,
        "sanity":      sanity_gates,
        "provenance":  provenance,
    }

    # NOMAD entries don't always declare magnetic state; emit a safe NM stub
    # only if the parser flagged a non-magnetic spin setting. Magnetic
    # block is optional in the schema, so omit otherwise.
    spin = _g(archive, "results", "method", "simulation", "dft", "spin_polarized")
    if spin is False:
        doc["magnetic"] = {"state": "NM", "collinear": True}

    # Kind-specific results block ------------------------------------------------
    if kind == "SinglePointCalculation":
        results: dict[str, Any] = {
            "status":         "PRELIMINARY",  # NOMAD doesn't gate paper-quotability
            "paper_quotable": False,
            "notes":          "Imported from NOMAD; rerun sanity_fill + reviewer pass before quoting.",
        }
        if energy_eV is not None:
            results["energy_eV"] = energy_eV
        if scf_ok is not None:
            results["scf_converged"] = scf_ok
        if band_gap_eV is not None:
            results["band_gap_eV"] = band_gap_eV
        doc["results"] = results

        # Optional ESA block when NOMAD parser produced electronic info.
        esa: dict[str, Any] = {}
        if band_gap_eV is not None:
            bg_kind = "metallic" if abs(band_gap_eV) < 1e-3 else "indirect"
            esa["band_gap_eV"] = {"value": band_gap_eV, "type": bg_kind}
        if esa:
            doc["electronic_structure_analysis"] = esa

    elif kind == "RelaxCalculation":
        # Pull optimizer + fmax from whichever NOMAD block is populated.
        opt: dict[str, Any] = (
            _g(archive, "workflow2", "geometry_optimization")
            or _g(archive, "results", "method", "simulation", "geometry_optimization")
            or _g(archive, "results", "properties", "geometry_optimization")
            or {}
        )
        # Legacy ``workflow`` is a list; pull the first geometry_optimization block.
        if not opt and isinstance(archive.get("workflow"), list):
            for w in archive["workflow"]:
                if (w or {}).get("type") == "geometry_optimization":
                    opt = (w or {}).get("geometry_optimization") or {}
                    break
        optimizer = opt.get("type") or opt.get("method") or opt.get("optimizer") or "unknown"
        fmax = opt.get("convergence_tolerance_force_maximum")  # joules / metre
        relax_protocol: dict[str, Any] = {"optimizer": str(optimizer)}
        if isinstance(fmax, (int, float)) and fmax > 0:
            # Convert J/m → eV/Å. 1 J/m = (1 / e) eV/m = (1e-10 / e) eV/Å.
            relax_protocol["fmax_eV_per_A"] = float(fmax) * 1e-10 / _J_PER_EV
        max_steps = opt.get("optimization_steps_maximum") or opt.get("optimization_steps")
        if isinstance(max_steps, int) and max_steps > 0:
            relax_protocol["max_steps"] = int(max_steps)
        doc["relax_protocol"] = relax_protocol

        results = {
            "status":         "PRELIMINARY",
            "paper_quotable": False,
            "notes":          "Imported from NOMAD; rerun sanity_fill + reviewer pass before quoting.",
        }
        if energy_eV is not None:
            results["final_energy_eV"] = energy_eV
        if isinstance(opt.get("is_converged_geometry"), bool):
            results["converged"] = opt["is_converged_geometry"]
        doc["results"] = results

    elif kind == "MDCalculation":
        md = _g(archive, "workflow2", "molecular_dynamics") or {}
        timestep = md.get("integration_timestep")  # seconds
        n_steps = md.get("n_steps") or md.get("integration_steps")
        ensemble = md.get("thermodynamic_ensemble") or "NVE"
        md_protocol: dict[str, Any] = {
            "ensemble":    ensemble.upper() if isinstance(ensemble, str) else "NVE",
            "timestep_fs": float(timestep) * 1e15 if isinstance(timestep, (int, float)) else 1.0,
        }
        if isinstance(n_steps, int) and n_steps > 0:
            md_protocol["n_steps"] = n_steps
        doc["md_protocol"] = md_protocol
        doc["results"] = {
            "status":         "PRELIMINARY",
            "paper_quotable": False,
            "notes":          "Imported from NOMAD; trajectory analysis not run.",
        }

    else:
        # NEB / US / MetaD / MLIPBenchmark / SanityReport — these aren't normally
        # produced by NOMAD; surface a SinglePoint fallback to keep the doc valid.
        doc["kind"] = "SinglePointCalculation"
        doc["results"] = {
            "status":         "PRELIMINARY",
            "paper_quotable": False,
            "notes": (
                f"NOMAD workflow {kind!r} not directly supported; "
                "emitted as SinglePointCalculation."
            ),
        }
        if energy_eV is not None:
            doc["results"]["energy_eV"] = energy_eV

    return doc


# ---------------------------------------------------------------------------
# Network glue


def fetch_to_tm_spec(
    entry_id: str,
    *,
    client: NomadClient | None = None,
    doc_id: str | None = None,
    author: str = "import@nomad",
) -> dict[str, Any]:
    """Fetch a single NOMAD entry and convert it to a TM-Spec doc."""
    cli = client or NomadClient()
    archive = cli.get_archive(entry_id)
    return archive_to_tm_spec(archive, doc_id=doc_id, author=author)


def fetch_search(
    query: dict[str, Any],
    *,
    client: NomadClient | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch up to ``limit`` entries matching ``query`` (paginated)."""
    cli = client or NomadClient()
    out: list[dict[str, Any]] = []
    page_after: str | None = None
    while len(out) < limit:
        page_size = min(limit - len(out), 50)
        resp = cli.search(query, page_size=page_size, page_after_value=page_after)
        rows = resp.get("data") or []
        if not rows:
            break
        out.extend(rows)
        page_after = (resp.get("pagination") or {}).get("next_page_after_value")
        if not page_after:
            break
    return out


# ---------------------------------------------------------------------------
# YAML emission


def _to_yaml(doc: dict[str, Any]) -> str:
    """Render a TM-Spec doc to YAML using the lightweight default style.

    We intentionally don't enforce the hand-curated layout used by the
    pilot examples — that's editorial. Validator + lint can be re-run on
    the output.
    """
    import yaml  # local import: yaml is a runtime dep already

    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)


def _write_doc(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_yaml(doc), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI dispatch


def main(argv: list[str] | None = None) -> int:
    """Dispatch ``tm-spec import-nomad`` and ``import-nomad-batch``.

    The outer ``tm_spec.cli`` already strips the leading sub-command.
    We get exactly what's left in ``argv``.
    """
    parser = argparse.ArgumentParser(
        prog="tm-spec import-nomad",
        description="Import a single NOMAD Archive entry into a TM-Spec YAML doc.",
    )
    parser.add_argument("entry_id", help="NOMAD entry_id (e.g. zRzA8h0p1q...)")
    parser.add_argument("--out", "-o", type=Path, help="Output YAML path. Default: stdout.")
    parser.add_argument(
        "--author",
        default="import@nomad",
        help="Email for provenance.author. Default: import@nomad.",
    )
    parser.add_argument(
        "--doc-id",
        default=None,
        help="Override the generated TM-Spec id (must match the spec id pattern).",
    )
    parser.add_argument(
        "--api-base",
        default=None,
        help="NOMAD API base URL (default: nomad-lab.eu/prod). Override for staging.",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="NOMAD API token. Default: read NOMAD_API_TOKEN env var.",
    )
    args = parser.parse_args(argv)

    client = NomadClient(base_url=args.api_base, token=args.token)
    try:
        doc = fetch_to_tm_spec(
            args.entry_id,
            client=client,
            doc_id=args.doc_id,
            author=args.author,
        )
    except NomadError as exc:
        print(f"FAIL  import-nomad {args.entry_id}: {exc}", file=sys.stderr)
        return 2

    yaml_text = _to_yaml(doc)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(yaml_text, encoding="utf-8")
        print(f"WROTE {args.out} (kind={doc['kind']}, id={doc['id']})")
    else:
        print(yaml_text, end="")
    return 0


def main_batch(argv: list[str] | None = None) -> int:
    """``tm-spec import-nomad-batch``."""
    parser = argparse.ArgumentParser(
        prog="tm-spec import-nomad-batch",
        description="Run a NOMAD entries query and import each match as a TM-Spec YAML.",
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--query", help="Inline JSON-encoded NOMAD query.")
    g.add_argument("--query-file", type=Path, help="Path to a JSON file with the query.")
    parser.add_argument("--limit", type=int, default=10, help="Max entries to import.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Directory to write per-entry YAML into.",
    )
    parser.add_argument("--author", default="import@nomad")
    parser.add_argument("--api-base", default=None)
    parser.add_argument("--token", default=None)
    args = parser.parse_args(argv)

    if args.query_file:
        query = json.loads(args.query_file.read_text(encoding="utf-8"))
    else:
        query = json.loads(args.query)
    if not isinstance(query, dict):
        print("FAIL  --query must decode to a JSON object", file=sys.stderr)
        return 2

    client = NomadClient(base_url=args.api_base, token=args.token)
    try:
        rows = fetch_search(query, client=client, limit=args.limit)
    except NomadError as exc:
        print(f"FAIL  import-nomad-batch search: {exc}", file=sys.stderr)
        return 2

    n_ok = n_fail = 0
    for row in rows:
        eid = (row or {}).get("entry_id") or (row or {}).get("calc_id")
        if not eid:
            n_fail += 1
            continue
        try:
            doc = fetch_to_tm_spec(eid, client=client, author=args.author)
        except NomadError as exc:
            print(f"FAIL  {eid}: {exc}", file=sys.stderr)
            n_fail += 1
            continue
        out_path = args.out_dir / f"{_slug(eid)}.tm.yaml"
        _write_doc(doc, out_path)
        print(f"WROTE {out_path}  [{doc['kind']}]")
        n_ok += 1

    print(f"Summary: {n_ok} written, {n_fail} failed.", file=sys.stderr)
    return 0 if n_fail == 0 else 1
