"""Import MAGNDATA (Bilbao Crystallographic Server) magnetic structures into TM-Spec.

MAGNDATA is the database of EXPERIMENTALLY determined magnetic structures (>2000
commensurate/incommensurate entries, magCIF/.mcif format, BNS magnetic space
groups). It is the *experimental* magnetic ground-truth anchor that complements
Materials Project *computed* magnetism (``importers.mp``): MP's collinear
small-cell enumeration can disagree with experiment (e.g. it labels troilite/
chalcopyrite FM where neutron diffraction finds AFM). This importer maps a magCIF
onto the TM-Spec ``magnetic`` block, recording ``geometry_origin: experimental``
and the authoritative ``bns_group``.

Architecture (mirrors ``importers.mp`` / ``importers.optimade``):

    parse_magcif(text)                 pure CIF parse -> field dict (offline)
    magcif_to_tm_spec(text, code=...)  pure transform -> tm-spec doc (offline)
    fetch_to_tm_spec(code, ...)        network glue: download .mcif -> doc

Ordering type (FM / AFM / ferri) is determined RIGOROUSLY from the magnetic
symmetry operations carried in the magCIF (``_space_group_symop_magn_operation.xyz``
include a time-reversal flag ±1): the net magnetisation is an axial vector that
must be invariant under every operation, so the symmetrisation projector
P = (1/|G|) Σ θ·det(R)·R over the rotation parts has a non-trivial image iff a
spontaneous net moment is symmetry-allowed (FM/ferri); rank 0 ⇒ antiferromagnet.
No external magnetic-point-group table is hardcoded — the verdict comes from the
file's own operations.

CLI (dispatched from ``tm_spec.cli``):

    tm-spec import-magndata --code 0.1 [--out FILE | --json]
    tm-spec import-magndata --mcif local.mcif --code 0.1   # parse a local file

Access: ``https://www.cryst.ehu.eus/magndata/mcif/<code>.mcif``. The Bilbao
server ships a misconfigured TLS certificate (hostname mismatch); for this public
reference data we fetch with certificate verification disabled (documented, opt-in
via ``verify_tls=False`` default for this host only).
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from .. import __version__ as TM_SPEC_VERSION

MAGNDATA_MCIF_URL = "https://www.cryst.ehu.eus/magndata/mcif/{code}.mcif"
USER_AGENT = f"tm-spec/{TM_SPEC_VERSION} (+https://github.com/exopoiesis)"
_MOMENT_EPS = 0.1  # |moment| (uB) below this is treated as zero


class MagndataError(RuntimeError):
    """Raised on HTTP / parse errors for a MAGNDATA entry."""


# ---------------------------------------------------------------------------
# magCIF parsing (minimal, stdlib)


def _strip_unc(tok: str) -> float | None:
    """Parse a CIF number that may carry a parenthesised uncertainty: 5.7461(2)."""
    m = re.match(r"^[+-]?\d*\.?\d+", tok.replace("(", " ").split()[0] if tok else "")
    try:
        return float(re.sub(r"\(.*\)", "", tok))
    except ValueError:
        return None


def _compress_formula(sum_str: str) -> str:
    """'La Mn O3' -> 'LaMnO3' (drop the CIF spaces between element-count tokens)."""
    return re.sub(r"\s+", "", sum_str.strip().strip("'\""))


def _formula_from_sites(parsed: dict) -> str | None:
    """Fallback formula from the asymmetric-unit ``_atom_site_type_symbol`` counts when
    ``_chemical_formula_sum`` is absent. Hill-ish order; APPROXIMATE (asymmetric unit,
    not the symmetry-expanded cell) -- enough to identify the chemistry/element set."""
    counts = parsed.get("site_elements")
    if not counts:
        return None
    def keyf(el):  # Hill: C, H first, then alphabetical
        return (0, "") if el == "C" else (1, "") if el == "H" else (2, el)
    return "".join(f"{el}{counts[el] if counts[el] > 1 else ''}" for el in sorted(counts, key=keyf))


def parse_magcif(text: str) -> dict[str, Any]:
    """Parse the fields TM-Spec needs from a magCIF. Pure, offline.

    Returns a dict with: formula, cell{a,b,c,alpha,beta,gamma}, bns_number,
    bns_name, point_group, propagation_vectors[list], symops[list of "xyz,θ"],
    moments[list of {label, mx, my, mz}].
    """
    out: dict[str, Any] = {"cell": {}, "propagation_vectors": [], "symops": [], "moments": []}
    lines = text.splitlines()
    i = 0

    def val(line: str) -> str:
        # "_tag   value" -> "value" (handles quotes)
        parts = line.split(None, 1)
        return parts[1].strip().strip("'\"").strip() if len(parts) > 1 else ""

    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        low = s.lower()
        if low.startswith("_chemical_formula_sum"):
            out["formula"] = _compress_formula(val(raw))
        elif low.startswith("_parent_space_group.it_number"):
            try:
                out["parent_sg"] = int(re.sub(r"\D", "", val(raw)))
            except (ValueError, TypeError):
                pass
        elif low.startswith("_space_group_magn.number_bns"):
            out["bns_number"] = val(raw)
        elif low.startswith("_space_group_magn.name_bns"):
            out["bns_name"] = re.sub(r"\s+", "", val(raw))
        elif low.startswith("_space_group_magn.point_group_name"):
            out["point_group"] = re.sub(r"\s+", "", val(raw))
        elif low.startswith("_cell_length_a"):
            out["cell"]["a"] = _strip_unc(val(raw))
        elif low.startswith("_cell_length_b"):
            out["cell"]["b"] = _strip_unc(val(raw))
        elif low.startswith("_cell_length_c"):
            out["cell"]["c"] = _strip_unc(val(raw))
        elif low.startswith("_cell_angle_alpha"):
            out["cell"]["alpha"] = _strip_unc(val(raw))
        elif low.startswith("_cell_angle_beta"):
            out["cell"]["beta"] = _strip_unc(val(raw))
        elif low.startswith("_cell_angle_gamma"):
            out["cell"]["gamma"] = _strip_unc(val(raw))
        elif low == "loop_":
            # collect the loop header tags, then the data rows.
            tags: list[str] = []
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith("_"):
                tags.append(lines[j].strip().lower())
                j += 1
            rows: list[str] = []
            while j < len(lines):
                t = lines[j].strip()
                if t == "" or t == "loop_" or t.startswith("_") or t.startswith("#"):
                    break
                rows.append(t)
                j += 1
            _consume_loop(tags, rows, out)
            i = j
            continue
        i += 1
    return out


def _consume_loop(tags: list[str], rows: list[str], out: dict[str, Any]) -> None:
    """Dispatch a parsed loop into propagation vectors / symops / moments."""
    tagset = set(tags)
    # propagation vectors: _parent_propagation_vector.kxkykz
    if any("propagation_vector.kxkykz" in t for t in tags):
        for r in rows:
            m = re.search(r"\[([^\]]+)\]", r)
            if m:
                comps = m.group(1).replace(",", " ").split()
                vec = []
                for c in comps:
                    try:
                        vec.append(float(Fraction(c)))
                    except (ValueError, ZeroDivisionError):
                        vec.append(0.0)
                if len(vec) == 3:
                    out["propagation_vectors"].append(vec)
        return
    # magnetic symmetry operations: _space_group_symop_magn_operation.xyz
    if any(t.endswith("_magn_operation.xyz") for t in tags):
        xyz_idx = next((k for k, t in enumerate(tags) if t.endswith(".xyz")), None)
        for r in rows:
            toks = r.split()
            # row like: "5 x+1/2,-y+1/2,-z+1/2,-1"  -> id then the xyz,θ string
            xyz = next((tok for tok in toks if "," in tok), None)
            if xyz is None and xyz_idx is not None and len(toks) > xyz_idx:
                xyz = toks[xyz_idx]
            if xyz:
                out["symops"].append(xyz)
        return
    # atom sites (for a formula fallback when _chemical_formula_sum is absent):
    # _atom_site_label / _atom_site_type_symbol / _atom_site_fract_*
    if "_atom_site_type_symbol" in tags and not any("_moment." in t for t in tags):
        ti = tags.index("_atom_site_type_symbol")
        counts: dict[str, int] = {}
        for r in rows:
            toks = r.split()
            if ti < len(toks):
                el = re.sub(r"[^A-Za-z].*$", "", toks[ti])  # 'Fe2+' / 'Fe' -> 'Fe'
                el = el[:1].upper() + el[1:].lower() if el else el
                if el:
                    counts[el] = counts.get(el, 0) + 1
        if counts:
            out["site_elements"] = counts
        return
    # atom site moments: _atom_site_moment.label / .crystalaxis_x/y/z
    if any(t.endswith("_moment.label") for t in tags):
        idx = {t.split(".")[-1]: k for k, t in enumerate(tags)}
        li = idx.get("label"); xi = idx.get("crystalaxis_x")
        yi = idx.get("crystalaxis_y"); zi = idx.get("crystalaxis_z")
        for r in rows:
            toks = r.split()
            if li is None or li >= len(toks):
                continue
            def g(k):
                v = _strip_unc(toks[k]) if (k is not None and k < len(toks)) else 0.0
                return v if v is not None else 0.0
            out["moments"].append({"label": toks[li], "mx": g(xi), "my": g(yi), "mz": g(zi)})
        return


# ---------------------------------------------------------------------------
# Ordering type from the magnetic symmetry operations (rigorous, file-self-contained)


def _symop_rotation_theta(xyz: str) -> tuple[list[list[int]], int]:
    """Parse 'x+1/2,-y+1/2,-z+1/2,-1' -> (3x3 rotation R, theta=±1).

    The first three comma fields are the spatial part (we keep only the linear
    coefficients of x,y,z); the trailing field is the time-reversal flag ±1.
    """
    fields = [f.strip() for f in xyz.split(",")]
    theta = 1
    if fields and re.fullmatch(r"[+-]?1", fields[-1]):
        theta = int(fields[-1])
        spatial = fields[:-1]
    else:
        spatial = fields[:3]
    R = [[0, 0, 0] for _ in range(3)]
    for row, comp in enumerate(spatial[:3]):
        for col, var in enumerate("xyz"):
            m = re.search(rf"([+-]?)\s*{var}", comp)
            if m:
                R[row][col] = -1 if m.group(1) == "-" else 1
    return R, theta


def _det3(R: list[list[int]]) -> int:
    return (R[0][0]*(R[1][1]*R[2][2]-R[1][2]*R[2][1])
            - R[0][1]*(R[1][0]*R[2][2]-R[1][2]*R[2][0])
            + R[0][2]*(R[1][0]*R[2][1]-R[1][1]*R[2][0]))


def _rank3(M: list[list[Fraction]]) -> int:
    """Rank of a 3x3 rational matrix via Gaussian elimination."""
    A = [row[:] for row in M]
    rank = 0
    for col in range(3):
        piv = next((r for r in range(rank, 3) if A[r][col] != 0), None)
        if piv is None:
            continue
        A[rank], A[piv] = A[piv], A[rank]
        pv = A[rank][col]
        A[rank] = [x / pv for x in A[rank]]
        for r in range(3):
            if r != rank and A[r][col] != 0:
                f = A[r][col]
                A[r] = [A[r][k] - f * A[rank][k] for k in range(3)]
        rank += 1
    return rank


def _axial_projector(symops: list[str]) -> list[list[Fraction]] | None:
    """Symmetrisation projector P = (1/|G|) Σ θ·det(R)·R for the axial vector M.

    M (net magnetisation) is invariant under the magnetic point group, so the net
    moment of a structure whose moments span direction v is P·v: its image is the
    symmetry-allowed net-moment subspace. Returns None if no operations parsed.
    """
    if not symops:
        return None
    n = len(symops)
    P = [[Fraction(0) for _ in range(3)] for _ in range(3)]
    for xyz in symops:
        R, theta = _symop_rotation_theta(xyz)
        s = theta * _det3(R)
        for a in range(3):
            for b in range(3):
                P[a][b] += Fraction(s * R[a][b], n)
    return P


def net_moment_allowed(symops: list[str]) -> bool | None:
    """True iff a spontaneous net moment is symmetry-allowed (rank(P) > 0)."""
    P = _axial_projector(symops)
    if P is None:
        return None
    return _rank3(P) > 0


def _net_moment_ratio(symops: list[str], moment_sum: tuple[float, float, float]) -> float | None:
    """|P · ΣM| / |ΣM| -- fraction of the structure's moment that survives the
    magnetic-symmetry projection. ~1 ⇒ ferromagnetic; ~0 ⇒ antiferromagnet (the
    moment lies in the symmetry-cancelled subspace); intermediate ⇒ canted/weak-FM.
    Distinguishes a true FM from a canted AFM far better than rank(P) alone
    (e.g. LaMnO3's moment is along the symmetry-cancelled axis -> ratio ≈ 0 = AFM)."""
    P = _axial_projector(symops)
    if P is None:
        return None
    import math
    total = math.sqrt(sum(c * c for c in moment_sum))
    if total < 1e-9:
        return 0.0
    pv = [float(sum(P[a][b] * Fraction(moment_sum[b]).limit_denominator(10**6) for b in range(3)))
          for a in range(3)]
    return math.sqrt(sum(c * c for c in pv)) / total


# ---------------------------------------------------------------------------
# Pure transform: magCIF -> TM-Spec doc


def _moment_magnitudes(parsed: dict) -> dict[str, float]:
    """Per-label moment magnitude (uB). Euclidean in crystal axes -- exact for
    orthogonal cells, approximate otherwise (flagged in the surrogate warning)."""
    out: dict[str, float] = {}
    for m in parsed.get("moments", []):
        mag = (m["mx"] ** 2 + m["my"] ** 2 + m["mz"] ** 2) ** 0.5
        out[m["label"]] = round(mag, 3)
    return out


def _classify_state(parsed: dict, mags: dict[str, float]) -> tuple[str, str | None]:
    """Return (magnetic_state, surrogate_warning) from moments + magnetic symmetry.

    Uses the net-moment ratio |P·ΣM|/|ΣM| (how much of the structure's moment
    survives the magnetic-symmetry projection): ~0 = AFM (moment cancels), ~1 = FM,
    intermediate = canted/weak-FM (dominant AFM) or ferri. This correctly calls a
    canted AFM (e.g. LaMnO3, moment on the cancelled axis) AFM rather than FM.
    """
    nonzero = [v for v in mags.values() if v >= _MOMENT_EPS]
    if not nonzero:
        return "NM", None
    pg = parsed.get("point_group")
    bns = parsed.get("bns_name")
    note_axes = "" if _is_orthogonal(parsed.get("cell", {})) else \
        " Cell non-orthogonal: |moment| is an approximate Euclidean magnitude."
    moment_sum = (
        sum(m["mx"] for m in parsed.get("moments", [])),
        sum(m["my"] for m in parsed.get("moments", [])),
        sum(m["mz"] for m in parsed.get("moments", [])),
    )
    ratio = _net_moment_ratio(parsed.get("symops", []), moment_sum)
    if ratio is None:
        return "AFM-G", (f"No magnetic symops parsed; FM/AFM not resolved. "
                         f"bns_group={bns} authoritative.{note_axes}")
    if ratio < 0.15:
        return "AFM-G", (f"Net moment ~cancels under magnetic symmetry "
                         f"(|P·ΣM|/|ΣM|={ratio:.2f}; point group {pg}) -> antiferromagnet "
                         f"(subtype A/C/G not distinguished). bns_group={bns} authoritative.{note_axes}")
    spread = (max(nonzero) - min(nonzero)) / max(nonzero) if max(nonzero) else 0.0
    if 0.15 <= ratio < 0.85:
        return "ferri", (f"Partial net moment (|P·ΣM|/|ΣM|={ratio:.2f}; point group {pg}) -> "
                         f"ferrimagnet / canted weak-FM. bns_group={bns} authoritative.{note_axes}")
    state = "ferri" if spread > 0.1 else "FM"
    return state, (f"Full net moment survives symmetry (|P·ΣM|/|ΣM|={ratio:.2f}; point group {pg}); "
                   f"FM vs ferri by moment spread={spread:.2f}. bns_group={bns} authoritative.{note_axes}")


def _is_orthogonal(cell: dict) -> bool:
    return all(abs((cell.get(k) or 90.0) - 90.0) < 1e-3 for k in ("alpha", "beta", "gamma"))


def _is_commensurate(parsed: dict) -> bool:
    for k in parsed.get("propagation_vectors", []):
        if any(abs(c - round(c)) > 1e-6 for c in k):
            return False
    return True


def magcif_to_tm_spec(
    text: str,
    *,
    code: str | None = None,
    doc_id: str | None = None,
    date: str | None = None,
    author: str = "import@magndata",
) -> dict[str, Any]:
    """Pure transformation: a MAGNDATA magCIF string -> TM-Spec/0.3 doc with an
    experimental ``magnetic`` block. No network."""
    parsed = parse_magcif(text)
    formula = parsed.get("formula") or _formula_from_sites(parsed) or "Unknown"
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    eid = code or "unknown"
    if doc_id is None:
        doc_id = f"tm.magndata.{re.sub(r'[^A-Za-z0-9_.+-]', '_', eid)}.{date}"

    mags = _moment_magnitudes(parsed)
    state, warn = _classify_state(parsed, mags)

    magnetic: dict[str, Any] = {"state": state, "collinear": _collinear(parsed)}
    if mags:
        magnetic["magmoms_uB"] = mags
    kvecs = parsed.get("propagation_vectors") or []
    if kvecs:
        magnetic["propagation_vector"] = kvecs[0]
    if parsed.get("bns_name"):
        magnetic["bns_group"] = parsed["bns_name"]
    if warn:
        magnetic["surrogate_warning"] = warn

    structure: dict[str, Any] = {
        "formula": formula,
        "chemical_formula_reduced": formula,
        "pbc": [True, True, True],
        "geometry_origin": "experimental",  # MAGNDATA = experimentally determined
    }
    if isinstance(parsed.get("parent_sg"), int):
        # the crystallographic PARENT space group (matches a structural/MP sg)
        structure["space_group"] = {"number": parsed["parent_sg"]}

    doc: dict[str, Any] = {
        "spec": "tm-spec/0.3",
        "kind": "SinglePointCalculation",
        "id": doc_id,
        "schema_url": "https://exopoiesis.github.io/tm-spec/0.3.json",
        "structure": structure,
        "calculation": {"method": "DFT"},  # placeholder; MAGNDATA is experimental refinement
        "magnetic": magnetic,
        "results": {
            "status": "PRELIMINARY",
            "paper_quotable": False,
            "notes": (
                "Imported from MAGNDATA (Bilbao): EXPERIMENTAL magnetic structure "
                f"(BNS {parsed.get('bns_number')} {parsed.get('bns_name')}). "
                "Structure is an experimental refinement, not a DFT calculation."
            ),
        },
        "sanity": [
            {"id": "G09_geometry_origin",
             "rule": "geometry_origin is dft_relaxed/dft_static, not an MLIP geometry",
             "observed": "experimental", "pass": "warn"},
        ],
        "provenance": {
            "date": date,
            "author": author,
            "import_source": {
                "archive": "other",  # MAGNDATA not in the archive enum -> other
                "entry_id": f"magndata:{eid}",
                "url": f"https://www.cryst.ehu.eus/magndata/index.php?index={eid}",
                "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "importer": f"tm-spec import-magndata@{TM_SPEC_VERSION}",
                "raw_keys": ["_chemical_formula_sum", "_space_group_magn.name_BNS",
                             "_parent_propagation_vector.kxkykz",
                             "_space_group_symop_magn_operation.xyz", "_atom_site_moment.*"],
            },
            "compute": {"host": "magndata", "cost_usd": 0.0},
        },
    }
    return doc


def _collinear(parsed: dict) -> bool:
    """True if all moment vectors are parallel (single common axis)."""
    vecs = [(m["mx"], m["my"], m["mz"]) for m in parsed.get("moments", [])
            if (m["mx"]**2 + m["my"]**2 + m["mz"]**2) ** 0.5 >= _MOMENT_EPS]
    if len(vecs) <= 1:
        return True
    import math
    v0 = vecs[0]
    n0 = math.sqrt(sum(c*c for c in v0))
    for v in vecs[1:]:
        nv = math.sqrt(sum(c*c for c in v))
        dot = sum(a*b for a, b in zip(v0, v))
        if abs(abs(dot) - n0 * nv) > 1e-2 * n0 * nv:
            return False
    return True


# ---------------------------------------------------------------------------
# Network glue


def _ssl_ctx(verify_tls: bool) -> ssl.SSLContext | None:
    if verify_tls:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_magcif(code: str, *, verify_tls: bool = False, timeout: float = 30.0) -> str:
    """Download a MAGNDATA .mcif by entry code (e.g. '0.1', '1.0.1', '2.10').

    ``verify_tls`` defaults False because the Bilbao server ships a misconfigured
    certificate; the data is public reference crystallography.
    """
    url = MAGNDATA_MCIF_URL.format(code=code)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx(verify_tls)) as r:
            text = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise MagndataError(f"MAGNDATA GET {url} -> HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise MagndataError(f"MAGNDATA GET {url} -> network error: {exc}") from exc
    if "_atom_site_moment" not in text and "_space_group_magn" not in text:
        raise MagndataError(f"MAGNDATA {code}: response is not a magCIF (got {len(text)}B)")
    return text


def fetch_to_tm_spec(code: str, *, verify_tls: bool = False, date: str | None = None,
                     author: str = "import@magndata", timeout: float = 30.0) -> dict[str, Any]:
    """Download a MAGNDATA entry by code and convert to a TM-Spec doc."""
    text = fetch_magcif(code, verify_tls=verify_tls, timeout=timeout)
    return magcif_to_tm_spec(text, code=code, date=date, author=author)


# ---------------------------------------------------------------------------
# CLI


def _to_yaml(doc: dict[str, Any]) -> str:
    import yaml
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="tm-spec import-magndata",
        description="Import a MAGNDATA experimental magnetic structure into a TM-Spec doc.",
    )
    p.add_argument("--code", required=True, help="MAGNDATA entry code, e.g. 0.1 / 1.0.1 / 2.10")
    p.add_argument("--mcif", type=Path, default=None, help="parse a LOCAL .mcif instead of fetching")
    p.add_argument("--verify-tls", action="store_true", help="verify the (misconfigured) Bilbao TLS cert")
    p.add_argument("--out", "-o", type=Path, default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--author", default="import@magndata")
    args = p.parse_args(argv)

    try:
        if args.mcif:
            text = args.mcif.read_text(encoding="utf-8")
            doc = magcif_to_tm_spec(text, code=args.code, author=args.author)
        else:
            doc = fetch_to_tm_spec(args.code, verify_tls=args.verify_tls, author=args.author)
    except MagndataError as exc:
        print(f"FAIL  import-magndata {args.code}: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(doc, indent=2, ensure_ascii=False) if args.json else _to_yaml(doc)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"WROTE {args.out} (magndata:{args.code}, state={doc['magnetic']['state']})")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
