"""Sanity checks on the JSON Schema itself.

These guard against accidental schema corruption (invalid JSON, broken
$ref, version drift between the package-bundled copy and the
repository-root copy).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, SchemaError

from tm_spec import SPEC_VERSION, schema_path


def test_schema_loads(schema: dict) -> None:
    assert isinstance(schema, dict)
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert schema.get("$id", "").endswith(f"tm-spec/{SPEC_VERSION}.json")


def test_schema_is_self_valid_jsonschema(schema: dict) -> None:
    """The schema MUST itself be a valid Draft 2020-12 JSON Schema."""
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as e:
        pytest.fail(f"Schema is not a valid Draft 2020-12 JSONSchema: {e}")


def test_schema_top_level_required(schema: dict) -> None:
    required = set(schema.get("required", []))
    expected = {"spec", "kind", "id", "structure", "calculation", "sanity", "provenance"}
    assert expected.issubset(required), (
        f"Top-level required fields drifted: missing {expected - required}"
    )


def test_kind_enum_complete(schema: dict) -> None:
    """All kinds documented in the spec must appear in the schema enum."""
    kinds = schema.get("$defs", {}).get("kind", {}).get("enum", [])
    for required in (
        "Structure", "Defects", "Magnetic", "Environment", "Reaction",
        "NEBCalculation", "USCalculation", "MetaDynCalculation",
        "MDCalculation", "MLIPBenchmark",
        "SinglePointCalculation", "RelaxCalculation",  # v0.2 (D-23/D-24)
        "SanityReport", "Provenance",
    ):
        assert required in kinds, f"Missing kind '{required}' in schema enum"


def test_status_enum(schema: dict) -> None:
    statuses = schema.get("$defs", {}).get("status", {}).get("enum", [])
    assert set(statuses) == {"PASS", "PRELIMINARY", "FAIL", "RETRACTED"}, (
        f"status enum changed; review D-13: {statuses}"
    )


def test_pass_value_enum(schema: dict) -> None:
    """D-15 — 4-value pass enum: true | false | "warn" | "skip"."""
    pass_value = schema.get("$defs", {}).get("pass_value", {})
    any_of = pass_value.get("anyOf", [])
    has_bool = any(branch.get("type") == "boolean" for branch in any_of)
    has_strings = any(
        sorted(branch.get("enum", [])) == ["skip", "warn"] for branch in any_of
    )
    assert has_bool and has_strings, (
        f"D-15: pass_value enum drift detected: {pass_value}"
    )


def test_bundled_copy_matches_repo_copy(repo_root: Path, schema: dict) -> None:
    """The package-bundled schema must be byte-identical to the repo copy.

    If this fails, run ``cp schemas/X.Y.json src/tm_spec/schemas/`` or
    vice versa, and update CHANGELOG.md.
    """
    bundled = json.loads(schema_path().read_text(encoding="utf-8"))
    repo = json.loads(
        (repo_root / "schemas" / f"{SPEC_VERSION}.json").read_text(encoding="utf-8")
    )
    assert bundled == repo, (
        "Bundled schema diverged from repo schema. Re-sync the two copies."
    )


def test_pages_copy_matches_repo_copy(repo_root: Path) -> None:
    """The schema also lives at ``docs/X.Y.json`` so that GitHub Pages serves
    it at the clean URL ``https://exopoiesis.github.io/tm-spec/X.Y.json``
    (matching the schema's ``$id``). Keep all three copies in sync.
    """
    repo = json.loads(
        (repo_root / "schemas" / f"{SPEC_VERSION}.json").read_text(encoding="utf-8")
    )
    pages = json.loads(
        (repo_root / "docs" / f"{SPEC_VERSION}.json").read_text(encoding="utf-8")
    )
    assert pages == repo, (
        "docs/X.Y.json diverged from schemas/X.Y.json. The Pages mirror "
        "must equal the canonical schema. Re-run "
        "``cp schemas/0.1.json docs/0.1.json``."
    )


def test_schema_version_consistent_with_package(schema: dict) -> None:
    """spec version baked into the schema $id must match SPEC_VERSION constant."""
    schema_id = schema.get("$id", "")
    assert SPEC_VERSION in schema_id, (
        f"SPEC_VERSION='{SPEC_VERSION}' not found in schema $id={schema_id!r}"
    )
