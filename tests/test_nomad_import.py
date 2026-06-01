"""Tests for ``tm_spec.importers.nomad``.

The importer has a pure transformation layer (NOMAD archive dict ->
TM-Spec dict) and a network layer. CI exercises only the pure layer with
cached NOMAD-shaped fixtures so the test suite remains offline.
"""
from __future__ import annotations

import json
from pathlib import Path

from tm_spec import validate_doc
from tm_spec.importers.nomad import archive_to_tm_spec


def _load_fixture(fixtures_dir: Path, name: str) -> dict:
    return json.loads((fixtures_dir / "nomad" / name).read_text(encoding="utf-8"))


def _gate(doc: dict, gate_id: str) -> dict | None:
    for g in doc.get("sanity", []):
        if g.get("id") == gate_id:
            return g
    return None


def test_archive_to_tm_spec_singlepoint_validates(fixtures_dir: Path) -> None:
    doc = archive_to_tm_spec(_load_fixture(fixtures_dir, "pyrite_singlepoint_archive.json"))
    assert doc["kind"] == "SinglePointCalculation"
    assert doc["spec"] == "tm-spec/0.3"
    assert doc["schema_url"] == "https://exopoiesis.github.io/tm-spec/0.3.json"
    assert doc["id"] == "tm.nomad.pyrite_sp_0001.2026-05-10"
    assert doc["structure"]["formula"] == "Fe32S64"
    assert doc["calculation"]["code"]["name"] == "QuantumESPRESSO"
    assert doc["results"]["energy_eV"] == -1000.0
    assert doc["results"]["band_gap_eV"] == 0.8

    # v0.3: single point -> dft_static, surfaced via the G09 sanity gate.
    g09 = _gate(doc, "G09_geometry_origin")
    assert g09 is not None
    assert g09["observed"] == "dft_static"
    assert g09["pass"] is True

    # schema auto-selected from the doc's own spec field (importer emits 0.3).
    schema_errs, rule_issues = validate_doc(doc)
    assert not schema_errs
    assert not [m for level, m in rule_issues if level == "error"]


def test_archive_to_tm_spec_relax_validates(fixtures_dir: Path) -> None:
    doc = archive_to_tm_spec(_load_fixture(fixtures_dir, "relax_archive.json"))
    assert doc["kind"] == "RelaxCalculation"
    assert doc["spec"] == "tm-spec/0.3"
    assert doc["schema_url"] == "https://exopoiesis.github.io/tm-spec/0.3.json"
    assert doc["id"] == "tm.nomad.relax_demo_0001.2026-05-10"
    assert doc["structure"]["formula"] == "Si2"
    assert doc["calculation"]["code"]["name"] == "VASP"
    assert doc["relax_protocol"]["optimizer"] == "BFGS"
    assert abs(doc["relax_protocol"]["fmax_eV_per_A"] - 0.05) < 1e-9
    assert doc["results"]["final_energy_eV"] == -8.0
    assert doc["results"]["converged"] is True

    # v0.3: relaxation -> dft_relaxed, surfaced via the G09 sanity gate.
    g09 = _gate(doc, "G09_geometry_origin")
    assert g09 is not None
    assert g09["observed"] == "dft_relaxed"
    assert g09["pass"] is True

    # schema auto-selected from the doc's own spec field (importer emits 0.3).
    schema_errs, rule_issues = validate_doc(doc)
    assert not schema_errs
    assert not [m for level, m in rule_issues if level == "error"]


def test_geometry_origin_mlip_relaxed(fixtures_dir: Path) -> None:
    """An MLIP-method relaxation must be tagged mlip_relaxed, not dft_relaxed."""
    doc = archive_to_tm_spec(_load_fixture(fixtures_dir, "mlip_relax_archive.json"))
    assert doc["kind"] == "RelaxCalculation"
    assert doc["spec"] == "tm-spec/0.3"
    assert doc["calculation"]["method"] == "MLIP"

    g09 = _gate(doc, "G09_geometry_origin")
    assert g09 is not None
    assert g09["observed"] == "mlip_relaxed"
    # mlip_relaxed is a non-blocking warn (energy comparisons need care).
    assert g09["pass"] == "warn"

    schema_errs, rule_issues = validate_doc(doc)
    assert not schema_errs
    assert not [m for level, m in rule_issues if level == "error"]


def test_imported_doc_is_prodromos_ready(fixtures_dir: Path) -> None:
    """Imported docs carry the structure + calculation.level provenance that
    prodromos parity / external-reference gates need."""
    doc = archive_to_tm_spec(_load_fixture(fixtures_dir, "pyrite_singlepoint_archive.json"))
    # formula -> element counts for G11_electron_parity + G19_external_reference.
    assert doc["structure"]["formula"]
    # calculation.level provenance (xc / basis / spin) for method comparison.
    level = doc["calculation"]["level"]
    assert level["xc"] == "GGA"
    assert level["basis"]["kind"] == "plane_waves"
    assert level["spin"] == "none"


def test_imported_docs_record_source_archive(fixtures_dir: Path) -> None:
    doc = archive_to_tm_spec(_load_fixture(fixtures_dir, "pyrite_singlepoint_archive.json"))
    source = doc["provenance"]["import_source"]
    assert source["archive"] == "nomad"
    assert source["entry_id"] == "pyrite_sp_0001"
    assert source["upload_id"] == "upload_pyrite_demo"
    assert "results.material" in source["raw_keys"]
    assert source["importer"].startswith("tm-spec import-nomad@")
