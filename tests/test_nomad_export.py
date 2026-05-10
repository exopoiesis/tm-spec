"""Tests for ``tm_spec.exporters.nomad`` — NOMAD upload bundle builder.

We don't talk to NOMAD itself; we only verify the local artefact tree
and ZIP contents, plus the rendered metadata YAMLs.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from tm_spec.exporters import nomad as nomad_exp


def test_render_readme_smoke(load_yaml, examples_dir: Path) -> None:
    doc = load_yaml(examples_dir / "pyr_smoke.tm.yaml")
    md = nomad_exp.render_readme(doc, "pyr_smoke.tm.yaml")
    assert "tm.pyr.vs.hint.smoke" in md
    assert "QuantumESPRESSO" in md
    assert "Sanity gates" in md
    assert "Provenance" in md


def test_render_nomad_metadata_yaml() -> None:
    text = nomad_exp.render_nomad_metadata(
        comment="bundle for test",
        references=["https://example.org/paper"],
        coauthors=["alice@example.org", "bob@example.org"],
        dataset_name="test-ds",
    )
    parsed = yaml.safe_load(text)
    assert parsed["comment"] == "bundle for test"
    assert parsed["references"] == ["https://example.org/paper"]
    assert "alice@example.org" in parsed["coauthors"]
    assert parsed["datasets"] == ["test-ds"]
    assert parsed["external_id"].startswith("tm-spec-")


def test_build_bundle_directory_layout(examples_dir: Path, tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    summary = nomad_exp.build_bundle(
        spec_paths=[
            examples_dir / "pyr_smoke.tm.yaml",
            examples_dir / "mack_vfe_neb.tm.yaml",
        ],
        bundle_dir=bundle_dir,
        raw_root=None,
        comment="smoke",
        references=[],
        coauthors=["t@example.org"],
        dataset_name="t",
    )

    # Top-level files
    assert (bundle_dir / "nomad.yaml").is_file()
    assert (bundle_dir / "README.md").is_file()
    assert (bundle_dir / "manifest.json").is_file()

    # Per-entry directories
    entries = [p for p in bundle_dir.iterdir() if p.is_dir()]
    assert len(entries) == 2

    for entry in entries:
        assert (entry / "tm_spec.yaml").is_file()
        assert (entry / "README.md").is_file()
        assert "sanity" in (entry / "tm_spec.yaml").read_text(encoding="utf-8")

    # Manifest agrees with the per-entry tree
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    ids_in_manifest = {e["id"] for e in manifest["entries"]}
    assert "tm.pyr.vs.hint.smoke.2026-04-29" in ids_in_manifest
    assert len(summary) == 2


def test_zip_bundle_creates_valid_zip(examples_dir: Path, tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    nomad_exp.build_bundle(
        spec_paths=[examples_dir / "pyr_smoke.tm.yaml"],
        bundle_dir=bundle_dir,
        raw_root=None,
        comment="smoke",
        references=[],
        coauthors=["t@example.org"],
        dataset_name="t",
    )

    zip_path = tmp_path / "out.zip"
    nomad_exp.zip_bundle(bundle_dir, zip_path)

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        # Top-level files inside bundle/
        assert any(n.endswith("nomad.yaml") for n in names)
        assert any(n.endswith("README.md") for n in names)
        # Per-entry artefacts
        assert any("tm_spec.yaml" in n for n in names)


def test_main_writes_zip(examples_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "ci_bundle.zip"
    rc = nomad_exp.main([
        str(examples_dir / "pyr_smoke.tm.yaml"),
        "--out", str(out),
        "--comment", "test bundle",
        "--coauthor", "alice@example.org",
        "--dataset", "ci-test",
    ])
    assert rc == 0
    assert out.exists()


def test_main_dry_run_skips_zip(examples_dir: Path, tmp_path: Path) -> None:
    target = tmp_path / "dry_bundle"
    rc = nomad_exp.main([
        str(examples_dir / "pyr_smoke.tm.yaml"),
        "--out", str(target),
        "--dry-run",
    ])
    assert rc == 0
    assert target.is_dir()
    # No ZIP next to it
    assert not (tmp_path / "dry_bundle.zip").exists()
