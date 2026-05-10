"""TM-Spec — Third Matter Specification reference implementation.

Public API surface (stable across 0.x):
    tm_spec.SPEC_VERSION                — "0.1"
    tm_spec.load_schema()               — return parsed JSON Schema dict
    tm_spec.validate_doc(doc)           — (schema_errors, rule_issues) tuple
    tm_spec.load_doc(path)              — parse YAML/JSON/JSONL into list of docs

Submodules:
    tm_spec.validator                   — schema + rule validator
    tm_spec.extract                     — AST-based stub generator
    tm_spec.lint                        — pilot vs paired-script diff
    tm_spec.sanity_fill                 — auto-fill sanity gates from artefacts
    tm_spec.exporters.nomad             — NOMAD upload bundle builder
    tm_spec.cli                         — argparse dispatch (`tm-spec` console script)
"""
from __future__ import annotations

from .validator import (
    SPEC_VERSION,
    load_doc,
    load_schema,
    schema_path,
    tm_specific_rules,
    validate_doc,
)

__all__ = [
    "SPEC_VERSION",
    "load_doc",
    "load_schema",
    "schema_path",
    "tm_specific_rules",
    "validate_doc",
]

__version__ = "0.1.0"
