"""Every bundled example MUST PASS the validator.

This is the canonical regression test for the spec: any change to the
schema that breaks an existing pilot is either a deliberate breaking
change (bump major) or a bug (revert).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tm_spec import validate_doc


@pytest.mark.parametrize(
    "name",
    [
        "pyr_smoke.tm.yaml",
        "mack_vfe_neb.tm.yaml",
        "w2_us_pmf.tm.yaml",
        "w2_metad.tm.yaml",
        "w1_grotthuss_aimd.tm.yaml",
        "w2_mlip_benchmark.tm.yaml",
    ],
)
def test_example_passes_schema(examples_dir: Path, name: str, load_yaml, schema) -> None:
    path = examples_dir / name
    assert path.exists(), f"missing example: {path}"
    doc = load_yaml(path)
    schema_errs, rule_issues = validate_doc(doc, schema)

    error_issues = [m for level, m in rule_issues if level == "error"]
    assert not schema_errs, f"{name} schema errors: {schema_errs}"
    assert not error_issues, f"{name} rule errors: {error_issues}"


def test_all_examples_have_required_top_level(all_examples, load_yaml) -> None:
    """Every example must declare spec, kind, id, structure, calc, sanity, provenance."""
    required = {"spec", "kind", "id", "structure", "calculation", "sanity", "provenance"}
    for path in all_examples:
        doc = load_yaml(path)
        missing = required - set(doc.keys())
        assert not missing, f"{path.name} missing required fields: {missing}"


def test_all_examples_use_current_spec_version(all_examples, load_yaml) -> None:
    """All shipped examples should declare the current spec version."""
    from tm_spec import SPEC_VERSION

    expected = f"tm-spec/{SPEC_VERSION}"
    for path in all_examples:
        doc = load_yaml(path)
        assert doc["spec"] == expected, (
            f"{path.name} declares spec={doc['spec']!r}, expected {expected!r}"
        )


def test_all_examples_have_unique_ids(all_examples, load_yaml) -> None:
    ids = [load_yaml(p)["id"] for p in all_examples]
    assert len(set(ids)) == len(ids), f"duplicate example IDs: {ids}"


def test_neb_examples_declare_paired_script(all_examples, load_yaml) -> None:
    """Every NEBCalculation pilot MUST name its paired Python script.

    NEB drivers are always Python (ASE), so the paired-script lint is
    expected to work on them. Other kinds (MD/US/MetaD/MLIPBenchmark)
    may be driven by code-native input files (CP2K .inp, ABACUS INPUT)
    and are exempt.
    """
    for path in all_examples:
        doc = load_yaml(path)
        if doc.get("kind") != "NEBCalculation":
            continue
        wf = doc.get("workflow", {}) or {}
        assert wf.get("paired_script"), (
            f"{path.name} is a NEBCalculation but lacks workflow.paired_script"
        )
