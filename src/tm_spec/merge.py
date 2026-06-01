"""Reusable, network-free merge engine for two TM-Spec documents.

Typical use: an importer produces a *deep but narrow* doc (a NOMAD archive
import — it has ``calculation.level`` / ``magnetic`` / ``results`` but only a
sparse ``structure``) and another importer produces a *shallow but broad* doc
(an OPTIMADE structures import — it has the canonical structure fields
``chemical_formula_*`` / ``lattice_vectors_A`` / ``pbc`` / ``dimension_types``
but no method, no energy). ``merge_docs`` folds the second into the first so the
NOMAD depth is preserved and the OPTIMADE structure holes are filled — locally,
with no manual editing and no network.

Semantics (``fill_only=True``, the default)
--------------------------------------------

    * Deep merge section-by-section. A *non-null* value already present in
      ``base`` is never overwritten; an overlay value only fills a hole
      (missing / ``None`` / empty container).
    * On a scalar conflict (both sides non-null, different) the base value is
      kept and a ``CONFLICT <path>: <a> vs <b>`` warning is emitted.
    * ``geometry_origin`` prefers the *more specific* value: a concrete
      ``dft_relaxed`` / ``dft_static`` / ``mlip_relaxed`` from base wins over an
      ``unknown`` overlay (and vice-versa) regardless of which side it is on.
    * ``provenance.parents`` / ``provenance.literature`` / ``provenance.decisions``
      are unioned (order-preserving, de-duplicated).
    * ``provenance.import_source`` from both docs is preserved as a list under
      ``provenance.import_source`` (so both the NOMAD and the OPTIMADE source are
      recorded).
    * ``sanity`` and ``preflight.gates`` are unioned by gate ``id`` (base wins on
      duplicate ids; overlay-only ids are appended).

Same-material guard
-------------------

    If the two docs describe different materials (their ``structure.formula`` /
    reduced formula disagree) the merge is almost certainly a bug. With
    ``strict_material=True`` (default) a :class:`MergeError` is raised; otherwise
    a warning is emitted and the merge proceeds.

The merged doc is always re-validatable (``validate_doc`` OK) when both inputs
were valid, because the merge only adds/keeps schema-valid fields.

CLI::

    tm-spec merge base.tm.yaml overlay.tm.yaml [--out FILE] [--json]
        [--allow-material-mismatch] [--overwrite]
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from .validator import load_doc

# geometry_origin specificity ranking: higher = more informative. ``unknown`` is
# the least specific (OPTIMADE); a concrete method-x-relaxation tag wins.
_GEOMETRY_ORIGIN_RANK: dict[str, int] = {
    "unknown":      0,
    "as_built":     1,
    "experimental": 2,
    "mlip_relaxed": 3,
    "dft_static":   4,
    "dft_relaxed":  5,
}

# provenance list-valued fields that should be unioned rather than fill-merged.
_PROVENANCE_LIST_KEYS = ("parents", "literature", "decisions")


class MergeError(ValueError):
    """Raised on a same-material guard violation (MATERIAL_MISMATCH)."""


# ---------------------------------------------------------------------------
# Helpers


def load_first_doc(path: Path) -> dict[str, Any]:
    """Load a single TM-Spec doc from YAML/JSON/JSONL (first doc if multiple)."""
    docs = load_doc(Path(path))
    if not docs:
        raise MergeError(f"no document found in {path}")
    if not isinstance(docs[0], dict):
        raise MergeError(f"top-level document in {path} is not a mapping")
    return docs[0]


def _formula_keys(doc: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return ``(formula, reduced)`` lowercased-stripped for material comparison."""
    struct = doc.get("structure") or {}
    if not isinstance(struct, dict):
        return None, None

    def _norm(v: Any) -> str | None:
        return v.strip() if isinstance(v, str) and v.strip() else None

    return _norm(struct.get("formula")), _norm(struct.get("chemical_formula_reduced"))


def _same_material(base: dict[str, Any], overlay: dict[str, Any]) -> bool:
    """True if base and overlay plausibly describe the same material.

    Compares the reduced formula first (most robust against supercell size),
    then the descriptive formula. If neither side declares any formula we cannot
    disprove sameness, so we return True (no false positive mismatch).
    """
    b_formula, b_reduced = _formula_keys(base)
    o_formula, o_reduced = _formula_keys(overlay)

    if b_reduced and o_reduced:
        return b_reduced == o_reduced
    if b_formula and o_formula:
        return b_formula == o_formula
    # Fall back to whatever single pair we have; if no overlap at all, allow.
    if b_reduced and o_formula:
        return b_reduced == o_formula
    if b_formula and o_reduced:
        return b_formula == o_reduced
    return True


def pick_same_material(
    base: dict[str, Any], candidates: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    """Pick the candidate that matches ``base``'s material.

    Returns ``(chosen, warnings)``. If several match the same material, the first
    is chosen. If none match, the first candidate is returned with a warning (the
    caller's strict_material guard then decides whether to error).
    """
    if not candidates:
        raise MergeError("no overlay candidates to merge")
    matches = [c for c in candidates if _same_material(base, c)]
    if matches:
        warns: list[str] = []
        if len(matches) > 1:
            warns.append(
                f"multiple OPTIMADE hits match the base material; merging the first "
                f"of {len(matches)}"
            )
        return matches[0], warns
    return candidates[0], [
        "no OPTIMADE hit matched the base material; merging the first candidate "
        "(use --allow-material-mismatch or fix the query)"
    ]


# ---------------------------------------------------------------------------
# Core deep merge


def _is_empty(v: Any) -> bool:
    """True for values that count as a 'hole' the overlay may fill."""
    if v is None:
        return True
    return isinstance(v, (dict, list, str)) and len(v) == 0


# Scalar paths that are expected to differ between two import sources (e.g. a NOMAD
# import and an OPTIMADE import of the same material): a conflict here is not signal,
# so we keep base silently instead of emitting a noisy CONFLICT warning.
_QUIET_CONFLICT_PATHS = frozenset({
    "provenance.date",
    "provenance.author",
    "provenance.compute.host",
})


def _merge_value(
    base_v: Any, over_v: Any, path: str, warnings: list[str], *, fill_only: bool
) -> Any:
    """Merge one value. Returns the merged value; appends conflict warnings."""
    # Overlay has nothing to contribute.
    if _is_empty(over_v):
        return base_v
    # Base has a hole -> take the overlay value.
    if _is_empty(base_v):
        return deepcopy(over_v)

    # Both present and non-empty.
    if isinstance(base_v, dict) and isinstance(over_v, dict):
        return _merge_dict(base_v, over_v, path, warnings, fill_only=fill_only)

    if isinstance(base_v, list) and isinstance(over_v, list):
        # Lists are treated atomically in fill_only mode: keep base (non-empty).
        # (Sanity/provenance lists are handled specially before reaching here.)
        if base_v != over_v:
            warnings.append(f"CONFLICT {path}: list differs (kept base)")
        return base_v

    # Scalars (or mismatched types).
    if base_v == over_v:
        return base_v
    if fill_only:
        if path not in _QUIET_CONFLICT_PATHS:
            warnings.append(f"CONFLICT {path}: {base_v!r} vs {over_v!r}")
        return base_v
    return deepcopy(over_v)


def _merge_dict(
    base: dict[str, Any], overlay: dict[str, Any], path: str, warnings: list[str],
    *, fill_only: bool,
) -> dict[str, Any]:
    """Deep-merge two dicts. ``base`` is copied; not mutated in place."""
    out = deepcopy(base)
    for key, over_v in overlay.items():
        sub_path = f"{path}.{key}" if path else key
        if key == "geometry_origin":
            out[key] = _merge_geometry_origin(out.get(key), over_v, warnings, sub_path)
            continue
        out[key] = _merge_value(out.get(key), over_v, sub_path, warnings, fill_only=fill_only)
    return out


def _merge_geometry_origin(
    base_v: Any, over_v: Any, warnings: list[str], path: str
) -> Any:
    """Prefer the more specific geometry_origin (higher rank)."""
    if _is_empty(base_v):
        return over_v
    if _is_empty(over_v):
        return base_v
    rb = _GEOMETRY_ORIGIN_RANK.get(str(base_v), -1)
    ro = _GEOMETRY_ORIGIN_RANK.get(str(over_v), -1)
    chosen = base_v if rb >= ro else over_v
    if base_v != over_v and rb >= 0 and ro >= 0:
        warnings.append(
            f"{path}: kept more specific geometry_origin {chosen!r} "
            f"(base={base_v!r}, overlay={over_v!r})"
        )
    return chosen


def _union_by_id(
    base_list: list[Any], over_list: list[Any], warnings: list[str], label: str
) -> list[Any]:
    """Union two lists of ``{id: ...}`` objects by id (base wins on dup id)."""
    out = [deepcopy(g) for g in base_list]
    seen = {g.get("id") for g in out if isinstance(g, dict)}
    for g in over_list:
        gid = g.get("id") if isinstance(g, dict) else None
        if gid is not None and gid in seen:
            continue  # base already has this gate id
        if gid is None and g in out:
            continue
        out.append(deepcopy(g))
        if gid is not None:
            seen.add(gid)
    return out


def _union_strings(base_list: list[Any], over_list: list[Any]) -> list[Any]:
    """Order-preserving de-duplicated union of two lists."""
    out = list(base_list)
    for v in over_list:
        if v not in out:
            out.append(v)
    return out


def _merge_provenance(
    base_prov: dict[str, Any], over_prov: dict[str, Any], warnings: list[str]
) -> dict[str, Any]:
    """Merge provenance: union list keys, collect both import_source records."""
    out = deepcopy(base_prov) if isinstance(base_prov, dict) else {}
    over = over_prov if isinstance(over_prov, dict) else {}

    for key, over_v in over.items():
        if key in _PROVENANCE_LIST_KEYS:
            base_v = out.get(key) or []
            if isinstance(base_v, list) and isinstance(over_v, list):
                out[key] = _union_strings(base_v, over_v)
            elif _is_empty(base_v):
                out[key] = deepcopy(over_v)
            continue
        if key == "import_source":
            out["import_source"] = _merge_import_source(out.get("import_source"), over_v)
            continue
        # date / author / compute / hash: fill-only.
        out[key] = _merge_value(out.get(key), over_v, f"provenance.{key}", warnings,
                                fill_only=True)
    return out


def _merge_import_source(base_src: Any, over_src: Any) -> Any:
    """Collect both import sources into a list (preserving both archives)."""
    def _as_list(v: Any) -> list[Any]:
        if v is None:
            return []
        if isinstance(v, list):
            return list(v)
        return [v]

    combined = _as_list(base_src) + _as_list(over_src)
    if not combined:
        return base_src
    # De-duplicate by (archive, entry_id).
    seen: set[tuple[Any, Any]] = set()
    out: list[Any] = []
    for s in combined:
        key = (s.get("archive"), s.get("entry_id")) if isinstance(s, dict) else (None, repr(s))
        if key in seen:
            continue
        seen.add(key)
        out.append(deepcopy(s))
    return out[0] if len(out) == 1 else out


# ---------------------------------------------------------------------------
# Public API


def merge_docs(
    base: dict[str, Any],
    overlay: dict[str, Any],
    *,
    fill_only: bool = True,
    strict_material: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """Merge ``overlay`` into ``base``. Returns ``(merged_doc, warnings)``.

    Parameters
    ----------
    base:
        The doc whose values take precedence (typically the deep NOMAD import).
    overlay:
        The doc supplying fills (typically the broad OPTIMADE import).
    fill_only:
        When True (default) base non-null scalars are never overwritten;
        overlay only fills holes. When False, overlay scalars win on conflict.
    strict_material:
        When True (default) a formula mismatch raises :class:`MergeError`
        (``MATERIAL_MISMATCH``); when False it is downgraded to a warning.

    Raises
    ------
    MergeError
        If the inputs are not mappings, or (with ``strict_material``) the two
        docs describe different materials.
    """
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        raise MergeError("both base and overlay must be mappings")

    warnings: list[str] = []

    if not _same_material(base, overlay):
        b_formula, b_reduced = _formula_keys(base)
        o_formula, o_reduced = _formula_keys(overlay)
        msg = (
            f"MATERIAL_MISMATCH: base ({b_formula or b_reduced!r}) and overlay "
            f"({o_formula or o_reduced!r}) describe different materials"
        )
        if strict_material:
            raise MergeError(msg)
        warnings.append(msg)

    out = deepcopy(base)

    for key, over_v in overlay.items():
        if key == "provenance":
            out["provenance"] = _merge_provenance(out.get("provenance") or {}, over_v, warnings)
            continue
        if key == "sanity":
            base_sanity = out.get("sanity") or []
            over_sanity = over_v or []
            if isinstance(base_sanity, list) and isinstance(over_sanity, list):
                out["sanity"] = _union_by_id(base_sanity, over_sanity, warnings, "sanity")
            continue
        if key == "preflight":
            out["preflight"] = _merge_preflight(out.get("preflight"), over_v, warnings)
            continue
        # spec / kind / id / schema_url: keep base (do not let overlay rewrite identity).
        if key in ("spec", "kind", "id", "schema_url"):
            if _is_empty(out.get(key)):
                out[key] = deepcopy(over_v)
            elif out.get(key) != over_v and key in ("kind",):
                warnings.append(f"CONFLICT {key}: {out.get(key)!r} vs {over_v!r} (kept base)")
            continue
        out[key] = _merge_value(out.get(key), over_v, key, warnings, fill_only=fill_only)

    return out, warnings


def _merge_preflight(base_pf: Any, over_pf: Any, warnings: list[str]) -> Any:
    """Merge preflight blocks: union gates by id, fill the rest."""
    if _is_empty(base_pf):
        return deepcopy(over_pf)
    if _is_empty(over_pf) or not isinstance(over_pf, dict) or not isinstance(base_pf, dict):
        return base_pf
    out = deepcopy(base_pf)
    for key, over_v in over_pf.items():
        if key == "gates":
            base_gates = out.get("gates") or []
            if isinstance(base_gates, list) and isinstance(over_v, list):
                out["gates"] = _union_by_id(base_gates, over_v, warnings, "preflight.gates")
            continue
        out[key] = _merge_value(out.get(key), over_v, f"preflight.{key}", warnings,
                                fill_only=True)
    return out


# ---------------------------------------------------------------------------
# CLI


def _to_yaml(doc: dict[str, Any]) -> str:
    import yaml

    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)


def main(argv: list[str] | None = None) -> int:
    """``tm-spec merge base overlay`` — fold overlay into base, locally."""
    parser = argparse.ArgumentParser(
        prog="tm-spec merge",
        description=(
            "Merge two TM-Spec docs (fill-only by default): base depth is kept, "
            "overlay fills the holes. Same-material guarded."
        ),
    )
    parser.add_argument("base", type=Path, help="Base doc (precedence; e.g. NOMAD import).")
    parser.add_argument("overlay", type=Path, help="Overlay doc (fills; e.g. OPTIMADE import).")
    parser.add_argument("--out", "-o", type=Path, help="Output path. Default: stdout.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of YAML.")
    parser.add_argument(
        "--allow-material-mismatch",
        action="store_true",
        help="Downgrade a formula mismatch from error to warning.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Let overlay scalars win on conflict (fill_only=False).",
    )
    args = parser.parse_args(argv)

    try:
        base = load_first_doc(args.base)
        overlay = load_first_doc(args.overlay)
    except Exception as exc:
        print(f"FAIL  merge: cannot load input: {exc}", file=sys.stderr)
        return 2

    try:
        merged, warns = merge_docs(
            base,
            overlay,
            fill_only=not args.overwrite,
            strict_material=not args.allow_material_mismatch,
        )
    except MergeError as exc:
        print(f"FAIL  merge: {exc}", file=sys.stderr)
        return 2

    for w in warns:
        print(f"WARN  {w}", file=sys.stderr)

    text = json.dumps(merged, indent=2) if args.json else _to_yaml(merged)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"WROTE {args.out} (kind={merged.get('kind')}, id={merged.get('id')})")
    else:
        print(text, end="" if args.json else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
