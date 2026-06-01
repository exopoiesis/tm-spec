"""Unit tests for TM-Spec rules beyond pure JSONSchema.

Each design decision that imposes a runtime check (D-14, D-15, D-16, D-19)
gets a positive *and* a negative test, so future regressions surface
as failing tests rather than silently accepted documents.
"""
from __future__ import annotations

import copy

import pytest

from tm_spec import tm_specific_rules, validate_doc

# ── D-14: paper_quotable must be boolean ──────────────────────────────────


def test_d14_paper_quotable_bool_pass(minimal_neb_doc) -> None:
    minimal_neb_doc["results"]["paper_quotable"] = True
    issues = tm_specific_rules(minimal_neb_doc)
    errors = [m for lvl, m in issues if lvl == "error"]
    assert not any("D-14" in m for m in errors)


def test_d14_paper_quotable_string_fails(minimal_neb_doc) -> None:
    minimal_neb_doc["results"]["paper_quotable"] = "yes"
    errors = [m for lvl, m in tm_specific_rules(minimal_neb_doc) if lvl == "error"]
    assert any("D-14" in m for m in errors)


def test_d14_paper_quotable_int_fails(minimal_neb_doc) -> None:
    minimal_neb_doc["results"]["paper_quotable"] = 1
    errors = [m for lvl, m in tm_specific_rules(minimal_neb_doc) if lvl == "error"]
    assert any("D-14" in m for m in errors)


# ── D-15: sanity[].pass enum ──────────────────────────────────────────────


@pytest.mark.parametrize("good", [True, False, "warn", "skip"])
def test_d15_pass_value_accepts_all_four(minimal_neb_doc, good) -> None:
    minimal_neb_doc["sanity"][0]["pass"] = good
    errors = [m for lvl, m in tm_specific_rules(minimal_neb_doc) if lvl == "error"]
    assert not any("D-15" in m for m in errors), errors


@pytest.mark.parametrize("bad", ["yes", "no", "ok", "true", 1, 0, None, [], {}])
def test_d15_rejects_unknown_pass_value(minimal_neb_doc, bad) -> None:
    minimal_neb_doc["sanity"][0]["pass"] = bad
    errors = [m for lvl, m in tm_specific_rules(minimal_neb_doc) if lvl == "error"]
    if bad is None:
        # `None` is covered by JSON-Schema "required: pass" rather than D-15.
        return
    assert any("D-15" in m for m in errors), (
        f"D-15 should reject pass={bad!r} but did not"
    )


# ── D-16: cost_usd must be numeric ────────────────────────────────────────


def test_d16_cost_usd_number_pass(minimal_neb_doc) -> None:
    minimal_neb_doc["provenance"]["compute"]["cost_usd"] = 4.0
    errors = [m for lvl, m in tm_specific_rules(minimal_neb_doc) if lvl == "error"]
    assert not any("D-16" in m for m in errors)


def test_d16_cost_usd_string_fails(minimal_neb_doc) -> None:
    minimal_neb_doc["provenance"]["compute"]["cost_usd"] = "~4"
    errors = [m for lvl, m in tm_specific_rules(minimal_neb_doc) if lvl == "error"]
    assert any("D-16" in m for m in errors)


# ── D-19: PRELIMINARY MetaDyn warns without quote_constraint ──────────────


def _make_metad_doc(minimal_neb_doc: dict) -> dict:
    """Coerce the minimal NEB doc into a (schema-incomplete but rule-checkable) MetaDyn."""
    doc = copy.deepcopy(minimal_neb_doc)
    doc["kind"] = "MetaDynCalculation"
    doc.pop("workflow", None)
    return doc


def test_d19_preliminary_without_quote_constraint_warns(minimal_neb_doc) -> None:
    doc = _make_metad_doc(minimal_neb_doc)
    doc["results"] = {"status": "PRELIMINARY", "paper_quotable": True}
    issues = tm_specific_rules(doc)
    warns = [m for lvl, m in issues if lvl == "warn"]
    assert any("D-19" in m for m in warns), warns


def test_d19_preliminary_with_quote_constraint_silent(minimal_neb_doc) -> None:
    doc = _make_metad_doc(minimal_neb_doc)
    doc["results"] = {
        "status":           "PRELIMINARY",
        "paper_quotable":    True,
        "quote_constraint": "lower_bound_only",
    }
    warns = [m for lvl, m in tm_specific_rules(doc) if lvl == "warn"]
    assert not any("D-19" in m for m in warns), warns


def test_d19_pass_status_silent(minimal_neb_doc) -> None:
    """D-19 should only fire on PRELIMINARY, not on PASS."""
    doc = _make_metad_doc(minimal_neb_doc)
    doc["results"] = {"status": "PASS", "paper_quotable": True}
    warns = [m for lvl, m in tm_specific_rules(doc) if lvl == "warn"]
    assert not any("D-19" in m for m in warns)


# ── Sanity gate ID uniqueness ─────────────────────────────────────────────


def test_duplicate_gate_ids_fail(minimal_neb_doc) -> None:
    minimal_neb_doc["sanity"] = [
        {"id": "G06_ascii_safe", "rule": "x", "pass": True},
        {"id": "G06_ascii_safe", "rule": "x dup", "pass": True},
    ]
    errors = [m for lvl, m in tm_specific_rules(minimal_neb_doc) if lvl == "error"]
    assert any("duplicate sanity gate" in m for m in errors)


def test_unique_gate_ids_silent(minimal_neb_doc) -> None:
    minimal_neb_doc["sanity"] = [
        {"id": "G01_FeS_bond",   "rule": "x", "pass": True},
        {"id": "G06_ascii_safe", "rule": "y", "pass": True},
    ]
    errors = [m for lvl, m in tm_specific_rules(minimal_neb_doc) if lvl == "error"]
    assert not any("duplicate sanity gate" in m for m in errors)


# ── End-to-end: minimal doc passes the full validator ─────────────────────


def test_minimal_doc_passes_full_validation(minimal_neb_doc) -> None:
    # schema auto-selected from the doc's own spec field.
    schema_errs, rule_issues = validate_doc(minimal_neb_doc)
    err_msgs = [m for lvl, m in rule_issues if lvl == "error"]
    assert not schema_errs, schema_errs
    assert not err_msgs, err_msgs
