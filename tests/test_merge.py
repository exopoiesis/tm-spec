"""Tests for ``tm_spec.merge`` — the reusable, network-free merge engine.

The canonical use is folding a broad-but-shallow OPTIMADE structure import
(the overlay) into a deep-but-narrow NOMAD method/results import (the base):
the merged doc keeps the NOMAD depth (calculation.level, magnetic, energy)
and gains the OPTIMADE width (formula variants, lattice_vectors, pbc) — and
must itself validate against schema 0.3.
"""
from __future__ import annotations

from typing import Any

from tm_spec import validate_doc
from tm_spec.merge import MergeError, merge_docs, pick_same_material


def _nomad_base() -> dict[str, Any]:
    """A deep NOMAD-like SinglePoint import (method depth, energy, magnetic)."""
    return {
        "spec": "tm-spec/0.3",
        "kind": "SinglePointCalculation",
        "id": "tm.nomad.fes_sp_0001.2026-06-01",
        "schema_url": "https://exopoiesis.github.io/tm-spec/0.3.json",
        "structure": {"formula": "Fe2S4", "geometry_origin": "dft_static"},
        "calculation": {
            "method": "DFT",
            "level": {"xc": "PBE", "spin": "collinear"},
            "code": {"name": "QuantumESPRESSO", "version": "7.3.1"},
        },
        "magnetic": {"state": "FM", "collinear": True},
        "results": {
            "status": "PRELIMINARY",
            "paper_quotable": False,
            "energy_eV": -123.4,
            "scf_converged": True,
        },
        "sanity": [{"id": "G05_scf_converged", "rule": "scf converged", "pass": True}],
        "provenance": {
            "date": "2026-06-01",
            "author": "import@nomad",
            "import_source": {"archive": "nomad", "entry_id": "fes_sp_0001"},
            "compute": {"host": "nomad-archive", "cost_usd": 0.0},
        },
    }


def _optimade_overlay(formula: str = "Fe2S4", reduced: str = "FeS2") -> dict[str, Any]:
    """A shallow OPTIMADE-like structure import (formula variants + lattice)."""
    return {
        "spec": "tm-spec/0.3",
        "kind": "SinglePointCalculation",
        "id": "tm.optimade_mp.mp-1522.2025-11-02",
        "schema_url": "https://exopoiesis.github.io/tm-spec/0.3.json",
        "structure": {
            "formula": formula,
            "chemical_formula_reduced": reduced,
            "chemical_formula_anonymous": "AB2",
            "lattice_vectors_A": [[5.42, 0.0, 0.0], [0.0, 5.42, 0.0], [0.0, 0.0, 5.42]],
            "pbc": [True, True, True],
            "dimension_types": [1, 1, 1],
            "geometry_origin": "unknown",
        },
        "calculation": {"method": "DFT"},
        "results": {"status": "PRELIMINARY", "paper_quotable": False},
        "sanity": [
            {"id": "G06_ascii_safe", "rule": "ascii", "pass": "skip"},
            {
                "id": "G09_geometry_origin",
                "rule": "geometry_origin",
                "observed": "unknown",
                "pass": "skip",
            },
        ],
        "provenance": {
            "date": "2025-11-02",
            "author": "import@optimade",
            "import_source": {"archive": "materials_project", "entry_id": "mp-1522"},
            "compute": {"host": "optimade:mp", "cost_usd": 0.0},
        },
    }


def _error_rules(rule_issues: list[tuple[str, str]]) -> list[str]:
    return [m for level, m in rule_issues if level == "error"]


def test_merge_keeps_nomad_depth_and_optimade_width() -> None:
    base = _nomad_base()
    overlay = _optimade_overlay()
    merged, _warns = merge_docs(base, overlay)

    # Depth from NOMAD preserved.
    assert merged["calculation"]["level"]["xc"] == "PBE"
    assert merged["calculation"]["level"]["spin"] == "collinear"
    assert merged["calculation"]["code"]["name"] == "QuantumESPRESSO"
    assert merged["magnetic"]["state"] == "FM"
    assert merged["results"]["energy_eV"] == -123.4
    assert merged["results"]["scf_converged"] is True

    # Width from OPTIMADE filled into the structure holes.
    assert merged["structure"]["chemical_formula_reduced"] == "FeS2"
    assert merged["structure"]["chemical_formula_anonymous"] == "AB2"
    assert "lattice_vectors_A" in merged["structure"]
    assert merged["structure"]["pbc"] == [True, True, True]
    assert merged["structure"]["dimension_types"] == [1, 1, 1]

    # Identity (kind/id/spec) stays the base's.
    assert merged["id"] == base["id"]
    assert merged["kind"] == "SinglePointCalculation"

    # Merged doc MUST validate.
    schema_errs, rule_issues = validate_doc(merged)
    assert not schema_errs, schema_errs
    assert not _error_rules(rule_issues), rule_issues

    # base must not be mutated.
    assert "lattice_vectors_A" not in _nomad_base()["structure"]


def test_geometry_origin_more_specific_wins() -> None:
    base = _nomad_base()  # dft_static
    overlay = _optimade_overlay()  # unknown
    merged, _ = merge_docs(base, overlay)
    assert merged["structure"]["geometry_origin"] == "dft_static"

    # And the reverse direction: a base 'unknown' takes the overlay's specific.
    base2 = _nomad_base()
    base2["structure"]["geometry_origin"] = "unknown"
    overlay2 = _optimade_overlay()
    overlay2["structure"]["geometry_origin"] = "dft_relaxed"
    merged2, _ = merge_docs(base2, overlay2)
    assert merged2["structure"]["geometry_origin"] == "dft_relaxed"


def test_both_import_sources_recorded() -> None:
    merged, _ = merge_docs(_nomad_base(), _optimade_overlay())
    isrc = merged["provenance"]["import_source"]
    assert isinstance(isrc, list)
    archives = {s["archive"] for s in isrc}
    assert archives == {"nomad", "materials_project"}


def test_sanity_union_by_id() -> None:
    merged, _ = merge_docs(_nomad_base(), _optimade_overlay())
    ids = {g["id"] for g in merged["sanity"]}
    assert ids == {"G05_scf_converged", "G06_ascii_safe", "G09_geometry_origin"}
    # No duplicate gate ids (validator would also flag this).
    all_ids = [g["id"] for g in merged["sanity"]]
    assert len(all_ids) == len(set(all_ids))


def test_same_material_guard_raises_on_mismatch() -> None:
    base = _nomad_base()
    overlay = _optimade_overlay(formula="CuO", reduced="CuO")
    try:
        merge_docs(base, overlay)
    except MergeError as exc:
        assert "MATERIAL_MISMATCH" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected MergeError on material mismatch")


def test_material_mismatch_downgraded_to_warning() -> None:
    base = _nomad_base()
    overlay = _optimade_overlay(formula="CuO", reduced="CuO")
    merged, warns = merge_docs(base, overlay, strict_material=False)
    assert any("MATERIAL_MISMATCH" in w for w in warns)
    # Still a valid doc (base material kept).
    schema_errs, rule_issues = validate_doc(merged)
    assert not schema_errs, schema_errs
    assert not _error_rules(rule_issues), rule_issues


def test_scalar_conflict_keeps_base_and_warns() -> None:
    base = _nomad_base()
    overlay = _optimade_overlay()
    # Give the overlay a conflicting code name (both non-null, different).
    overlay["calculation"] = {"method": "DFT", "code": {"name": "VASP"}}
    merged, warns = merge_docs(base, overlay)
    assert merged["calculation"]["code"]["name"] == "QuantumESPRESSO"  # base kept
    assert any("CONFLICT" in w and "code.name" in w for w in warns), warns


def test_overwrite_mode_lets_overlay_win() -> None:
    base = _nomad_base()
    overlay = _optimade_overlay()
    overlay["calculation"] = {"method": "DFT", "code": {"name": "VASP"}}
    merged, _ = merge_docs(base, overlay, fill_only=False)
    assert merged["calculation"]["code"]["name"] == "VASP"  # overlay won


def test_pick_same_material_chooses_match() -> None:
    base = _nomad_base()
    cands = [
        _optimade_overlay(formula="CuO", reduced="CuO"),
        _optimade_overlay(formula="Fe2S4", reduced="FeS2"),
    ]
    chosen, _warns = pick_same_material(base, cands)
    assert chosen["structure"]["chemical_formula_reduced"] == "FeS2"


def test_pick_same_material_no_match_warns() -> None:
    base = _nomad_base()
    cands = [_optimade_overlay(formula="CuO", reduced="CuO")]
    chosen, warns = pick_same_material(base, cands)
    assert chosen is cands[0]
    assert warns and "no OPTIMADE hit matched" in warns[0]


def test_merge_rejects_non_mapping() -> None:
    try:
        merge_docs(_nomad_base(), ["not", "a", "dict"])  # type: ignore[arg-type]
    except MergeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected MergeError for non-mapping overlay")
