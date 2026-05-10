"""Tests for the AST-based extractor.

These guard against regressions in static parsing of typical
ASE/QE/CP2K/MACE Python scripts. The fixture script
``tests/fixtures/scripts/fixture_neb_qe.py`` exercises every code path
the extractor needs (argparse defaults, ``crystal()``, ``Espresso()``,
nested ``input_data``, ``NEB``/``BFGS``/``FIRE``).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tm_spec import SPEC_VERSION, validate_doc
from tm_spec import extract as extract_mod


@pytest.fixture
def fixture_script(fixtures_dir: Path) -> Path:
    return fixtures_dir / "scripts" / "fixture_neb_qe.py"


@pytest.fixture
def extracted(fixture_script: Path) -> dict:
    yaml_text, _ = extract_mod.extract(fixture_script)
    return yaml.safe_load(yaml_text)


# ── Static AST extraction ─────────────────────────────────────────────────


def test_extract_returns_yaml_string(fixture_script: Path) -> None:
    yaml_text, ins = extract_mod.extract(fixture_script)
    assert isinstance(yaml_text, str)
    assert yaml_text.startswith("# Auto-extracted")
    assert f"spec: tm-spec/{SPEC_VERSION}" in yaml_text
    assert ins is not None


def test_extract_detects_neb_kind(extracted: dict) -> None:
    assert extracted["kind"] == "NEBCalculation"


def test_extract_detects_qe_code(extracted: dict) -> None:
    assert extracted["calculation"]["code"]["name"] == "QuantumESPRESSO"


def test_extract_method_is_dft(extracted: dict) -> None:
    assert extracted["calculation"]["method"] == "DFT"


def test_extract_picks_argparse_cutoff(extracted: dict) -> None:
    basis = extracted["calculation"]["level"]["basis"]
    assert basis["cutoff_Ry"] == 60
    assert basis["rho_cutoff_Ry"] == 240


def test_extract_picks_argparse_kmesh(extracted: dict) -> None:
    assert extracted["calculation"]["k_points"]["mesh"] == [2, 2, 2]


def test_extract_picks_n_images(extracted: dict) -> None:
    assert extracted["workflow"]["n_images"] == 7


def test_extract_picks_optimizer_fire(extracted: dict) -> None:
    """When both BFGS (endpoints) and FIRE (NEB) appear, NEB workflow uses FIRE."""
    assert extracted["workflow"]["optimizer"] == "FIRE"


def test_extract_picks_kspring(extracted: dict) -> None:
    assert extracted["workflow"]["k_spring_eV_per_A2"] == 0.10


def test_extract_detects_idpp_prewrap(extracted: dict) -> None:
    assert extracted["workflow"]["prewrap"] == "idpp"


def test_extract_picks_supercell_and_pbc(extracted: dict) -> None:
    assert extracted["structure"]["supercell"] == [2, 2, 2]
    assert extracted["structure"]["pbc"] == [True, True, True]


def test_extract_picks_pyrite_prototype(extracted: dict) -> None:
    """Spacegroup 205 in the script must trigger the AB2_cP12_205_a_c hint."""
    assert extracted["structure"]["prototype"] == "AB2_cP12_205_a_c"
    assert extracted["structure"]["space_group"]["number"] == 205


def test_extract_nspin1_yields_NM_state(extracted: dict) -> None:
    """nspin=1 in the script's input_data must produce magnetic.state=NM."""
    assert extracted["magnetic"]["state"] == "NM"
    assert extracted["calculation"]["level"]["spin"] == "none"


def test_extract_picks_smearing(extracted: dict) -> None:
    smearing = extracted["calculation"]["level"]["smearing"]
    assert smearing["kind"] == "gaussian"
    assert smearing["width_Ry"] == 0.005


# ── Generated YAML must validate ──────────────────────────────────────────


def test_extracted_yaml_passes_schema(extracted: dict, schema: dict) -> None:
    """Every extractor stub must be parseable AND PASS the validator with
    only TODO_HUMAN placeholders."""
    schema_errs, rule_issues = validate_doc(extracted, schema)
    err_msgs = [m for lvl, m in rule_issues if lvl == "error"]
    assert not schema_errs, f"extractor produced invalid YAML: {schema_errs}"
    assert not err_msgs, f"extractor stub fails rule check: {err_msgs}"


def test_extract_writes_to_disk(fixture_script: Path, tmp_path: Path) -> None:
    """The CLI ``main`` writes a file; verify it round-trips through YAML."""
    out = tmp_path / "extracted.tm.yaml"
    rc = extract_mod.main([str(fixture_script), "--out", str(out)])
    assert rc == 0
    assert out.exists()
    doc = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert doc["kind"] == "NEBCalculation"
    assert doc["calculation"]["code"]["name"] == "QuantumESPRESSO"


# ── Robustness ────────────────────────────────────────────────────────────


def test_extract_missing_script_returns_2(tmp_path: Path) -> None:
    rc = extract_mod.main([str(tmp_path / "nope.py"), "--out", str(tmp_path / "x.yaml")])
    assert rc == 2


def test_extract_empty_script_does_not_crash(tmp_path: Path) -> None:
    """An empty Python file must produce a Structure stub, not a traceback."""
    src = tmp_path / "empty.py"
    src.write_text("", encoding="utf-8")
    yaml_text, _ = extract_mod.extract(src)
    doc = yaml.safe_load(yaml_text)
    assert doc["kind"] == "Structure"
