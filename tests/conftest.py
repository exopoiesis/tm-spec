"""Shared pytest fixtures for the tm-spec test suite.

Conventions:
    - ``REPO_ROOT`` is the absolute path to the repository root (the
      directory containing ``pyproject.toml``).
    - ``examples_dir`` yields the path to the bundled examples folder.
    - ``schema`` yields the bundled JSON Schema dict.
    - ``fixtures_dir`` yields the path to ``tests/fixtures``.
    - ``load_yaml`` is a small helper to parse a TM-Spec YAML file with
      datetime normalisation already applied (matches what the validator
      does).

Tests SHOULD prefer these fixtures over hand-rolled paths so that moving
the repo or running from a different cwd does not break them.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from tm_spec import load_doc, load_schema

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def examples_dir() -> Path:
    d = REPO_ROOT / "examples"
    assert d.exists(), f"examples directory not found at {d}"
    return d


@pytest.fixture(scope="session")
def all_examples(examples_dir: Path) -> list[Path]:
    files = sorted(examples_dir.glob("*.tm.yaml"))
    assert files, "no example *.tm.yaml found"
    return files


@pytest.fixture(scope="session")
def schemas_dir() -> Path:
    d = REPO_ROOT / "schemas"
    assert d.exists()
    return d


@pytest.fixture(scope="session")
def schema() -> dict[str, Any]:
    return load_schema()


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    d = Path(__file__).parent / "fixtures"
    assert d.exists()
    return d


@pytest.fixture
def load_yaml():
    """Return a function that loads a YAML file with datetime normalisation."""

    def _load(path: Path) -> dict[str, Any]:
        docs = load_doc(path)
        assert len(docs) == 1, f"expected single doc, got {len(docs)} in {path}"
        return docs[0]

    return _load


@pytest.fixture
def minimal_neb_doc() -> dict[str, Any]:
    """Smallest possible NEBCalculation document that PASSes the validator.

    Tests that mutate this doc MUST deepcopy first — pytest reuses the
    fixture across function-scope users only via lookup, but mutation
    inside a test would leak via reference assignment.
    """
    return copy.deepcopy(_MINIMAL_NEB)


# A canonical minimal valid NEBCalculation doc, kept in code (not as YAML)
# so it stays in sync with schema changes during refactors. Mirror of
# tests/fixtures/minimal_neb.tm.yaml.
_MINIMAL_NEB: dict[str, Any] = {
    "spec": "tm-spec/0.2",
    "kind": "NEBCalculation",
    "id":   "tm.fix.minimal.neb.2026-01-01",
    "structure": {
        "formula":   "Fe4S8",
        "prototype": "AB2_cP12_205_a_c",
        "supercell": [1, 1, 1],
        "pbc":       [True, True, True],
    },
    "magnetic": {"state": "NM", "collinear": True},
    "calculation": {
        "method": "DFT",
        "level":  {
            "xc":    "PBE",
            "basis": {"kind": "plane_waves", "cutoff_Ry": 60},
            "spin":  "none",
        },
        "k_points": {"mesh": [2, 2, 2]},
        "code":     {"name": "QuantumESPRESSO", "version": "7.3.1"},
    },
    "workflow": {
        "kind":      "NEB",
        "stage":     "smoke",
        "endpoints": {
            "A": {"ref": "A.extxyz", "E_eV": -100.0, "fmax": 0.04},
            "B": {"ref": "B.extxyz", "E_eV": -100.0, "fmax": 0.04},
        },
        "optimizer":     "BFGS",
        "fmax_eV_per_A": 0.05,
    },
    "results": {"status": "PASS", "paper_quotable": False},
    "sanity":  [
        {"id": "G06_ascii_safe", "rule": "no em-dash in script", "pass": True},
    ],
    "provenance": {
        "date":    "2026-01-01",
        "author":  "test@example.com",
        "compute": {"host": "ci", "cost_usd": 0.0},
        "hash": {
            "inputs":  "sha256:placeholder_minimal_doc",
            "outputs": "sha256:placeholder_minimal_doc",
        },
    },
}
