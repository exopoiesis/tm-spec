"""Versioning consistency tests.

Ensure that:
    - ``tm_spec.SPEC_VERSION`` matches the schema $id.
    - The schema filename in ``schemas/`` matches SPEC_VERSION.
    - Every example's ``spec:`` field points at the current version.
    - The package ``__version__`` is parseable as SemVer.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import tm_spec

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def test_package_version_is_semver() -> None:
    assert SEMVER_RE.match(tm_spec.__version__), (
        f"Package version {tm_spec.__version__!r} is not SemVer-formatted."
    )


def test_spec_version_format() -> None:
    """SPEC_VERSION should be MAJOR.MINOR (no patch — the spec is not patched)."""
    assert re.match(r"^\d+\.\d+$", tm_spec.SPEC_VERSION), (
        f"SPEC_VERSION='{tm_spec.SPEC_VERSION}' should be MAJOR.MINOR"
    )


def test_schema_file_matches_spec_version(repo_root: Path) -> None:
    schemas_dir = repo_root / "schemas"
    expected = f"{tm_spec.SPEC_VERSION}.json"
    assert (schemas_dir / expected).exists(), (
        f"schemas/{expected} not found. Did SPEC_VERSION change without renaming the schema?"
    )


def test_schema_id_matches_spec_version(schema: dict) -> None:
    schema_id = schema.get("$id", "")
    assert tm_spec.SPEC_VERSION in schema_id, (
        f"SPEC_VERSION='{tm_spec.SPEC_VERSION}' not present in schema $id={schema_id!r}"
    )
    assert schema_id.endswith(f"{tm_spec.SPEC_VERSION}.json")


def test_schema_const_spec_field(schema: dict) -> None:
    """The ``spec:`` field must be ``const: tm-spec/<version>``."""
    spec_field = schema.get("properties", {}).get("spec", {})
    assert spec_field.get("const") == f"tm-spec/{tm_spec.SPEC_VERSION}", (
        f"schema property 'spec' const drifted: {spec_field}"
    )


def test_changelog_mentions_current_version(repo_root: Path) -> None:
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert tm_spec.__version__ in changelog, (
        f"CHANGELOG.md does not mention package version {tm_spec.__version__}"
    )


def test_pyproject_version_matches_package(repo_root: Path) -> None:
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version         = "{tm_spec.__version__}"' in pyproject, (
        f"pyproject.toml version drifted from package __version__={tm_spec.__version__}"
    )


def test_citation_cff_version_matches(repo_root: Path) -> None:
    cff = (repo_root / "CITATION.cff").read_text(encoding="utf-8")
    assert f'version: "{tm_spec.__version__}"' in cff, (
        "CITATION.cff version drifted from package __version__"
    )


def test_bundled_schema_loadable_from_package() -> None:
    """The bundled JSON must be valid JSON when loaded via the package path helper."""
    path = tm_spec.schema_path()
    assert path.exists()
    json.loads(path.read_text(encoding="utf-8"))
