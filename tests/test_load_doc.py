"""Tests for ``tm_spec.load_doc`` — YAML/JSON/JSONL ingestion + datetime normalisation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tm_spec import load_doc


def test_load_yaml_returns_singleton_list(examples_dir: Path) -> None:
    docs = load_doc(examples_dir / "pyr_smoke.tm.yaml")
    assert len(docs) == 1
    assert docs[0]["kind"] == "NEBCalculation"


def test_yaml_date_is_normalised_to_string(examples_dir: Path) -> None:
    docs = load_doc(examples_dir / "pyr_smoke.tm.yaml")
    date_value = docs[0]["provenance"]["date"]
    assert isinstance(date_value, str), (
        f"YAML date was not normalised to ISO string: {type(date_value).__name__}"
    )
    assert date_value == "2026-04-29"


def test_load_jsonl_returns_one_doc_per_line(tmp_path: Path) -> None:
    p = tmp_path / "stream.jsonl"
    p.write_text(
        '\n'.join([
            json.dumps({"spec": "tm-spec/0.1", "kind": "Structure", "id": "a"}),
            json.dumps({"spec": "tm-spec/0.1", "kind": "Defects", "id": "b"}),
            "",  # blank line skipped
            json.dumps({"spec": "tm-spec/0.1", "kind": "Provenance", "id": "c"}),
        ]),
        encoding="utf-8",
    )
    docs = load_doc(p)
    assert len(docs) == 3
    assert [d["kind"] for d in docs] == ["Structure", "Defects", "Provenance"]


def test_load_json_returns_singleton(tmp_path: Path) -> None:
    p = tmp_path / "doc.json"
    p.write_text(json.dumps({"spec": "tm-spec/0.1", "kind": "Structure"}), encoding="utf-8")
    docs = load_doc(p)
    assert docs == [{"spec": "tm-spec/0.1", "kind": "Structure"}]


def test_load_unknown_extension_raises(tmp_path: Path) -> None:
    p = tmp_path / "x.toml"
    p.write_text("ignored", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        load_doc(p)
