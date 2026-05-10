"""Tests for ``tm_spec.lint`` — pilot ↔ paired-script diff.

The fixtures pair a synthetic pilot YAML against two synthetic Python
scripts:

    fixture_neb_pilot.tm.yaml      → fixture_neb_qe.py        (in-sync)
    fixture_neb_pilot_drift.tm.yaml → fixture_neb_qe_drift.py (drifted)

The first must PASS; the second must FAIL with errors on cutoff_Ry and
k-mesh, plus warnings on n_images and k_spring.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

from tm_spec import lint as lint_mod

# ── In-sync pilot: PASS ───────────────────────────────────────────────────


def test_lint_passes_when_pilot_matches_script(repo_root: Path, fixtures_dir: Path) -> None:
    pilot = fixtures_dir / "fixture_neb_pilot.tm.yaml"

    buf = io.StringIO()
    with redirect_stdout(buf):
        verdict = lint_mod.lint_one(pilot, repo_root=repo_root)
    output = buf.getvalue()

    assert verdict is True, f"expected PASS, got verdict={verdict!r}\n{output}"
    assert "PASS" in output
    assert "mismatched_err=0" in output
    assert "mismatched_warn=0" in output


# ── Drifted pilot: FAIL with specific mismatches ──────────────────────────


def test_lint_detects_drift(repo_root: Path, fixtures_dir: Path) -> None:
    pilot = fixtures_dir / "fixture_neb_pilot_drift.tm.yaml"

    buf = io.StringIO()
    with redirect_stdout(buf):
        verdict = lint_mod.lint_one(pilot, repo_root=repo_root)
    output = buf.getvalue()

    assert verdict is False, f"expected FAIL, got verdict={verdict!r}\n{output}"
    assert "FAIL" in output

    # Expected error-severity drifts (cutoff + k-mesh)
    assert "PW cutoff" in output
    assert "k-mesh" in output

    # Expected warn-severity drifts (n_images + k_spring)
    assert "NEB images" in output
    assert "NEB spring k" in output


def test_lint_strict_mode_fails_on_warns_only(
    repo_root: Path, fixtures_dir: Path, tmp_path: Path
) -> None:
    """A pilot whose only drift is in warn-severity fields fails with --strict."""
    # Build a one-off pilot with ONLY n_images drift (warn) — manually crafted
    pilot = tmp_path / "warn_only.tm.yaml"
    src_pilot = (fixtures_dir / "fixture_neb_pilot.tm.yaml").read_text(encoding="utf-8")
    pilot.write_text(
        src_pilot.replace("n_images:           7", "n_images:           99"),
        encoding="utf-8",
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        verdict = lint_mod.lint_one(pilot, repo_root=repo_root, strict=True)
    output = buf.getvalue()

    assert verdict is False, f"expected FAIL under --strict\n{output}"
    assert "WARN" not in output.split("\n")[0]  # first-line verdict is FAIL


# ── No paired_script: SKIP ────────────────────────────────────────────────


def test_lint_skips_doc_without_paired_script(
    repo_root: Path, tmp_path: Path, examples_dir: Path
) -> None:
    """A pilot lacking ``workflow.paired_script`` is silently skipped."""
    bench_pilot = tmp_path / "no_paired.tm.yaml"
    src = (examples_dir / "w2_mlip_benchmark.tm.yaml").read_text(encoding="utf-8")
    bench_pilot.write_text(src, encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        verdict = lint_mod.lint_one(bench_pilot, repo_root=repo_root)

    assert verdict is True
    assert "SKIP" in buf.getvalue()


def test_lint_fails_when_paired_script_missing(
    repo_root: Path, tmp_path: Path, fixtures_dir: Path
) -> None:
    """Pilot points at a paired_script that does not exist on disk."""
    pilot_path = tmp_path / "broken.tm.yaml"
    src = (fixtures_dir / "fixture_neb_pilot.tm.yaml").read_text(encoding="utf-8")
    pilot_path.write_text(
        src.replace(
            "paired_script:      tests/fixtures/scripts/fixture_neb_qe.py",
            "paired_script:      tests/fixtures/scripts/THIS_DOES_NOT_EXIST.py",
        ),
        encoding="utf-8",
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        verdict = lint_mod.lint_one(pilot_path, repo_root=repo_root)
    output = buf.getvalue()

    assert verdict is False
    assert "paired_script not found" in output
