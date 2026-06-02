"""Tests for ``tm_spec.importers.mp`` (Materials Project magnetic-depth importer).

Like the NOMAD / OPTIMADE importers, MP has a pure transform layer (an MP summary
record [+ magnetism record] -> TM-Spec doc) and a network layer. CI exercises the
pure layer with in-memory MP-shaped dicts, plus the network glue with MPClient._get
monkeypatched, so the suite stays fully offline.
"""
from __future__ import annotations

from typing import Any

import pytest

from tm_spec import validate_doc
from tm_spec.importers import mp as mpimp
from tm_spec.importers.mp import (
    MPClient,
    MPError,
    fetch_to_tm_spec,
    summary_to_tm_spec,
)


def _no_error_rules(rule_issues: list[tuple[str, str]]) -> list[str]:
    return [m for level, m in rule_issues if level == "error"]


# -- pure transform: magnetic-state mapping ---------------------------------

def test_nm_pyrite_maps_to_NM_and_validates() -> None:
    summary = {"material_id": "mp-226", "formula_pretty": "FeS2",
               "symmetry": {"number": 205}, "is_magnetic": False, "ordering": "NM",
               "total_magnetization": 0.0, "num_magnetic_sites": 0}
    mag = {"material_id": "mp-226", "ordering": "NM", "magmoms": [0.0] * 12}
    doc = summary_to_tm_spec(summary, mag, date="2026-06-02")

    assert doc["spec"] == "tm-spec/0.3"
    assert doc["kind"] == "SinglePointCalculation"
    assert doc["structure"]["formula"] == "FeS2"
    assert doc["structure"]["space_group"]["number"] == 205
    assert doc["structure"]["geometry_origin"] == "dft_relaxed"
    assert doc["magnetic"]["state"] == "NM"
    assert doc["magnetic"]["collinear"] is True
    assert doc["provenance"]["import_source"]["archive"] == "materials_project"
    assert doc["provenance"]["import_source"]["entry_id"] == "mp-226"

    schema_errs, rule_issues = validate_doc(doc)
    assert schema_errs == [], schema_errs
    assert _no_error_rules(rule_issues) == []


def test_afm_maps_to_AFM_G_with_warning() -> None:
    summary = {"material_id": "mp-2282", "formula_pretty": "NiS2",
               "symmetry": {"number": 205}, "is_magnetic": True, "ordering": "AFM"}
    mag = {"magmoms": [1.3, 1.3, -1.3, -1.3, 0.0, 0.0]}
    doc = summary_to_tm_spec(summary, mag, date="2026-06-02")
    assert doc["magnetic"]["state"] == "AFM-G"
    assert "AFM" in doc["magnetic"]["surrogate_warning"]
    # per-site magmoms preserved
    assert doc["magnetic"]["magmoms_uB"]["0"] == 1.3
    assert doc["magnetic"]["magmoms_uB"]["2"] == -1.3
    assert validate_doc(doc)[0] == []


def test_fim_maps_to_ferri() -> None:
    summary = {"material_id": "mp-21515", "formula_pretty": "Fe3S4",
               "symmetry": {"number": 227}, "is_magnetic": True, "ordering": "FiM"}
    doc = summary_to_tm_spec(summary, {"magmoms": [4, 4, -3.9, 0, 0, 0, 0]}, date="2026-06-02")
    assert doc["magnetic"]["state"] == "ferri"
    assert validate_doc(doc)[0] == []


def test_fm_maps_to_FM() -> None:
    summary = {"material_id": "mp-2070", "formula_pretty": "CoS2",
               "symmetry": {"number": 205}, "is_magnetic": True, "ordering": "FM"}
    doc = summary_to_tm_spec(summary, {"magmoms": [1.0, 0, 0]}, date="2026-06-02")
    assert doc["magnetic"]["state"] == "FM"
    assert "surrogate_warning" not in doc["magnetic"]
    assert validate_doc(doc)[0] == []


def test_unknown_ordering_inferred_from_moment_and_flagged() -> None:
    # ordering missing -> infer from moment, with a surrogate_warning.
    big = {"material_id": "mp-x", "formula_pretty": "FeS", "symmetry": {"number": 194},
           "is_magnetic": True, "ordering": "Unknown"}
    doc = summary_to_tm_spec(big, {"magmoms": [2.4, 2.4]}, date="2026-06-02")
    assert doc["magnetic"]["state"] == "FM"  # 2.4/TM > 0.5
    assert "inferred from moment" in doc["magnetic"]["surrogate_warning"]

    small = {"material_id": "mp-y", "formula_pretty": "FeS2", "symmetry": {"number": 205},
             "is_magnetic": False, "ordering": None}
    doc2 = summary_to_tm_spec(small, {"magmoms": [0.0, 0.0]}, date="2026-06-02")
    assert doc2["magnetic"]["state"] == "NM"


def test_summary_to_tm_spec_rejects_non_dict() -> None:
    with pytest.raises(MPError):
        summary_to_tm_spec("not-a-dict")  # type: ignore[arg-type]


# -- network glue (monkeypatched _get) --------------------------------------

def test_fetch_to_tm_spec_formula_sg_picks_stable(monkeypatch: Any) -> None:
    # two FeS2 polymorphs at different sg; ask for sg205 -> exactly pyrite (mp-226).
    summary_rows = [
        {"material_id": "mp-226", "formula_pretty": "FeS2", "symmetry": {"number": 205},
         "is_magnetic": False, "ordering": "NM", "energy_above_hull": 0.0},
        {"material_id": "mp-1522", "formula_pretty": "FeS2", "symmetry": {"number": 58},
         "is_magnetic": False, "ordering": "NM", "energy_above_hull": 0.01},
    ]

    def fake_get(self: MPClient, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if path == "/materials/summary/":
            return {"data": summary_rows}
        if path == "/materials/magnetism/":
            return {"data": [{"material_id": "mp-226", "magmoms": [0.0] * 12}]}
        raise AssertionError(path)

    monkeypatch.setattr(MPClient, "_get", fake_get)
    docs = fetch_to_tm_spec(formula="FeS2", space_group=205, client=MPClient(api_key="x"),
                            date="2026-06-02")
    assert len(docs) == 1
    assert docs[0]["provenance"]["import_source"]["entry_id"] == "mp-226"
    assert docs[0]["magnetic"]["state"] == "NM"
    assert validate_doc(docs[0])[0] == []


def test_client_requires_api_key(monkeypatch: Any) -> None:
    monkeypatch.delenv("MP_API_KEY", raising=False)
    with pytest.raises(MPError):
        MPClient()._get("/materials/summary/", {})
