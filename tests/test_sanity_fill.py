"""Tests for ``tm_spec.sanity_fill`` — auto-fill ``sanity[].observed/pass``.

Drives the function with synthetic JSON + extxyz fixtures whose values
hit every recognised gate.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from tm_spec import sanity_fill as sf

# ── parse_extxyz_min_FeS ──────────────────────────────────────────────────


def test_parse_extxyz_min_FeS_reasonable(fixtures_dir: Path) -> None:
    d = sf.parse_extxyz_min_FeS(fixtures_dir / "xyz" / "relaxed_pristine.xyz")
    assert d is not None
    # Synthetic structure has Fe at (0,0,0) and S at (1.311,1.311,1.311)
    # → distance = sqrt(3 * 1.311²) ≈ 2.270 Å
    assert 2.20 < d < 2.30, f"unexpected min Fe-S = {d}"


def test_parse_extxyz_min_FeS_short_distance(fixtures_dir: Path) -> None:
    d = sf.parse_extxyz_min_FeS(fixtures_dir / "xyz" / "relaxed_short_FeS.xyz")
    assert d == 1.5, f"expected 1.5 Å, got {d}"


def test_parse_extxyz_handles_missing_file(tmp_path: Path) -> None:
    nope = tmp_path / "nope.xyz"
    with pytest.raises(FileNotFoundError):
        sf.parse_extxyz_min_FeS(nope)


def test_parse_extxyz_returns_none_when_no_FeS(tmp_path: Path) -> None:
    """A file with neither Fe nor S returns None rather than crashing."""
    xyz = tmp_path / "wrong.xyz"
    xyz.write_text("2\nCu only\nCu 0 0 0\nCu 1 0 0\n", encoding="utf-8")
    assert sf.parse_extxyz_min_FeS(xyz) is None


# ── fill_from_json ────────────────────────────────────────────────────────


@pytest.fixture
def pyr_smoke_doc(examples_dir: Path) -> dict:
    """Use the bundled pyrite smoke pilot - it has every gate G01-G09 we test."""
    return yaml.safe_load((examples_dir / "pyr_smoke.tm.yaml").read_text(encoding="utf-8"))


def test_fill_from_json_passes_all_gates(pyr_smoke_doc, fixtures_dir: Path) -> None:
    doc = copy.deepcopy(pyr_smoke_doc)
    updates = sf.fill_from_json(doc, fixtures_dir / "neb_json" / "canonical_result.json")
    assert updates, "no gates were updated — IDs may have drifted"

    by_id = {g["id"]: g for g in doc["sanity"] if isinstance(g, dict)}

    # Every gate that the JSON drives must end up True
    for gid in (
        "G04_fmax_endpoints",
        "G09_endpoint_symmetry",
        "G05_scf_converged",
        "G08_idpp_prewrap",
    ):
        assert by_id[gid]["pass"] is True, f"{gid} did not pass: {by_id[gid]}"

    # G04 records the fmax pair we put in the JSON
    assert by_id["G04_fmax_endpoints"]["observed"] == [0.027, 0.026]
    # G09 records the dE
    assert by_id["G09_endpoint_symmetry"]["observed"] == 0.0002


def test_fill_from_json_failure_path(pyr_smoke_doc, fixtures_dir: Path) -> None:
    doc = copy.deepcopy(pyr_smoke_doc)
    sf.fill_from_json(doc, fixtures_dir / "neb_json" / "canonical_result_failures.json")
    by_id = {g["id"]: g for g in doc["sanity"] if isinstance(g, dict)}
    # All these must end up False (gate detected the bad value)
    for gid in (
        "G04_fmax_endpoints",
        "G09_endpoint_symmetry",
        "G05_scf_converged",
    ):
        assert by_id[gid]["pass"] is False, f"{gid} should have failed"


def test_fill_from_json_respects_fmax_target(pyr_smoke_doc, fixtures_dir: Path) -> None:
    doc = copy.deepcopy(pyr_smoke_doc)
    # Target tighter than 0.027: should now FAIL G04
    sf.fill_from_json(
        doc,
        fixtures_dir / "neb_json" / "canonical_result.json",
        fmax_target=0.01,
    )
    by_id = {g["id"]: g for g in doc["sanity"] if isinstance(g, dict)}
    assert by_id["G04_fmax_endpoints"]["pass"] is False


# ── fill_from_xyz ─────────────────────────────────────────────────────────


def test_fill_from_xyz_pass(pyr_smoke_doc, fixtures_dir: Path) -> None:
    doc = copy.deepcopy(pyr_smoke_doc)
    updates = sf.fill_from_xyz(doc, fixtures_dir / "xyz" / "relaxed_pristine.xyz")
    assert updates
    by_id = {g["id"]: g for g in doc["sanity"] if isinstance(g, dict)}
    assert by_id["G01_FeS_bond"]["pass"] is True
    assert 2.20 < by_id["G01_FeS_bond"]["observed"] < 2.30


def test_fill_from_xyz_fail(pyr_smoke_doc, fixtures_dir: Path) -> None:
    """Short Fe-S distance must flip the gate to False."""
    doc = copy.deepcopy(pyr_smoke_doc)
    sf.fill_from_xyz(doc, fixtures_dir / "xyz" / "relaxed_short_FeS.xyz")
    by_id = {g["id"]: g for g in doc["sanity"] if isinstance(g, dict)}
    assert by_id["G01_FeS_bond"]["pass"] is False


def test_fill_from_xyz_threshold_override(pyr_smoke_doc, fixtures_dir: Path) -> None:
    """Caller can raise the threshold to make a normally-passing structure fail."""
    doc = copy.deepcopy(pyr_smoke_doc)
    sf.fill_from_xyz(
        doc, fixtures_dir / "xyz" / "relaxed_pristine.xyz", fes_threshold_A=2.5
    )
    by_id = {g["id"]: g for g in doc["sanity"] if isinstance(g, dict)}
    # 2.27 is now below the 2.50 threshold → fail
    assert by_id["G01_FeS_bond"]["pass"] is False


# ── End-to-end via main() ─────────────────────────────────────────────────


def test_main_writes_output_yaml(
    examples_dir: Path, fixtures_dir: Path, tmp_path: Path
) -> None:
    out_path = tmp_path / "out.tm.yaml"
    rc = sf.main([
        str(examples_dir / "pyr_smoke.tm.yaml"),
        "--json", str(fixtures_dir / "neb_json" / "canonical_result.json"),
        "--xyz",  str(fixtures_dir / "xyz" / "relaxed_pristine.xyz"),
        "--out",  str(out_path),
    ])
    assert rc == 0
    assert out_path.exists()
    doc = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert doc["kind"] == "NEBCalculation"
    by_id = {g["id"]: g for g in doc["sanity"] if isinstance(g, dict)}
    assert by_id["G01_FeS_bond"]["pass"] is True
