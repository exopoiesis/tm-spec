"""Tests for ``tm_spec.importers.optimade``.

Like the NOMAD importer, the OPTIMADE importer has a pure transformation
layer (an OPTIMADE ``structures`` JSON response -> TM-Spec docs) and a
network layer. CI exercises the pure layer with an in-memory
Materials-Project-shaped payload, plus the network glue with the HTTP
GET monkeypatched, so the suite stays fully offline.
"""
from __future__ import annotations

from typing import Any

from tm_spec import validate_doc
from tm_spec.importers import optimade as opt
from tm_spec.importers.optimade import (
    OptimadeError,
    _parse_optimade_structures,
    build_filter,
    import_optimade,
    structure_to_tm_spec,
)

# A Materials-Project-shaped OPTIMADE structures response (one ordered FeS2).
MP_PAYLOAD: dict[str, Any] = {
    "data": [
        {
            "id": "mp-1522",
            "type": "structures",
            "attributes": {
                "chemical_formula_descriptive": "Fe2S4",
                "chemical_formula_reduced": "FeS2",
                "chemical_formula_anonymous": "AB2",
                "elements": ["Fe", "S"],
                "nelements": 2,
                "lattice_vectors": [
                    [5.42, 0.0, 0.0],
                    [0.0, 5.42, 0.0],
                    [0.0, 0.0, 5.42],
                ],
                "dimension_types": [1, 1, 1],
                "nperiodic_dimensions": 3,
                "structure_features": [],
                "last_modified": "2025-11-02T08:30:00Z",
            },
        }
    ],
    "meta": {"data_returned": 1, "data_available": 1},
}


def _no_error_rules(rule_issues: list[tuple[str, str]]) -> list[str]:
    return [m for level, m in rule_issues if level == "error"]


def test_parse_optimade_structures_validates() -> None:
    docs = _parse_optimade_structures(MP_PAYLOAD, provider="mp")
    assert len(docs) == 1
    doc = docs[0]

    assert doc["spec"] == "tm-spec/0.3"
    assert doc["kind"] == "SinglePointCalculation"
    assert doc["schema_url"] == "https://exopoiesis.github.io/tm-spec/0.3.json"

    # formula mapping: descriptive preferred for structure.formula.
    assert doc["structure"]["formula"] == "Fe2S4"
    assert doc["structure"]["chemical_formula_reduced"] == "FeS2"
    assert doc["structure"]["chemical_formula_anonymous"] == "AB2"
    assert doc["structure"]["lattice_vectors_A"][0] == [5.42, 0.0, 0.0]

    # pbc + dimension_types from OPTIMADE.
    assert doc["structure"]["pbc"] == [True, True, True]
    assert doc["structure"]["dimension_types"] == [1, 1, 1]

    # OPTIMADE never reports relaxation status -> honest "unknown".
    assert doc["structure"]["geometry_origin"] == "unknown"

    # minimal calculation + PRELIMINARY results.
    assert doc["calculation"] == {"method": "DFT"}
    assert doc["results"]["status"] == "PRELIMINARY"
    assert doc["results"]["paper_quotable"] is False

    # provenance.import_source records the MP provider + id.
    isrc = doc["provenance"]["import_source"]
    assert isrc["archive"] == "materials_project"
    assert isrc["entry_id"] == "mp-1522"

    # MUST validate against schema 0.3.
    schema_errs, rule_issues = validate_doc(doc)
    assert not schema_errs, schema_errs
    assert not _no_error_rules(rule_issues), rule_issues


def test_pbc_from_nperiodic_dimensions_only() -> None:
    """When dimension_types is absent, fall back to nperiodic_dimensions."""
    entry = {
        "id": "x-1",
        "type": "structures",
        "attributes": {
            "chemical_formula_descriptive": "C",
            "nperiodic_dimensions": 2,  # slab
        },
    }
    doc = structure_to_tm_spec(entry, provider="mp")
    assert doc["structure"]["pbc"] == [True, True, False]
    assert doc["structure"]["dimension_types"] == [1, 1, 0]
    schema_errs, _ = validate_doc(doc)
    assert not schema_errs, schema_errs


def test_geometry_origin_always_unknown() -> None:
    doc = structure_to_tm_spec(MP_PAYLOAD["data"][0], provider="mp")
    assert doc["structure"]["geometry_origin"] == "unknown"
    g09 = next(g for g in doc["sanity"] if g["id"] == "G09_geometry_origin")
    assert g09["observed"] == "unknown"
    assert g09["pass"] == "skip"


def test_offline_returns_empty(monkeypatch) -> None:
    """live=False must not touch the network and returns []."""

    def _boom(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("network must not be hit in offline mode")

    monkeypatch.setattr(opt, "_http_get_json", _boom)
    assert import_optimade(["Fe", "S"], live=False) == []


def test_empty_response_returns_empty() -> None:
    assert _parse_optimade_structures({"data": []}) == []
    assert _parse_optimade_structures([]) == []


def test_import_optimade_live_path_monkeypatched(monkeypatch) -> None:
    """Exercise the network glue with the HTTP GET stubbed out."""
    captured: dict[str, Any] = {}

    def _fake_get(url: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
        captured["url"] = url
        captured["params"] = params
        return MP_PAYLOAD

    monkeypatch.setattr(opt, "_http_get_json", _fake_get)
    docs = import_optimade(["Fe", "S"], reduced_formula="FeS2", provider="mp")
    assert len(docs) == 1
    assert docs[0]["structure"]["formula"] == "Fe2S4"
    # reduced_formula preferred over elements in the built filter.
    assert captured["params"]["filter"] == 'chemical_formula_reduced="FeS2"'
    assert captured["url"] == opt.PROVIDERS["mp"]


def test_build_filter_variants() -> None:
    assert build_filter(["Fe", "S"]) == 'elements HAS ALL "Fe","S"'
    assert build_filter(None, reduced_formula="FeS2") == 'chemical_formula_reduced="FeS2"'
    assert build_filter(["Fe"], raw_filter="nelements=2") == "nelements=2"


def test_build_filter_requires_something() -> None:
    try:
        build_filter(None, None, None)
    except OptimadeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected OptimadeError for empty filter")


def test_unknown_provider_raises() -> None:
    try:
        import_optimade(["Fe", "S"], provider="does-not-exist")
    except OptimadeError as exc:
        assert "unknown provider" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected OptimadeError for unknown provider")
