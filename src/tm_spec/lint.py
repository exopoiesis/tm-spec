"""TM-Spec lint — diff hand-crafted pilot YAML against ``paired_script``.

Catches inconsistencies like *"pilot has cutoff_Ry=80 but the real script
defaults to 60"* that lead to non-reproducible documentation. Run before
submission to verify each pilot is an accurate snapshot of its paired
Python script.

Usage::

    tm-spec lint examples/pyr_smoke.tm.yaml
    tm-spec lint --all examples/
    tm-spec lint --strict examples/mack_vfe_neb.tm.yaml
"""
from __future__ import annotations

import argparse
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import yaml

from . import extract as extract_mod

# Diff fields: (yaml_path, label, severity_on_mismatch)
DIFF_FIELDS: list[tuple[str, str, str]] = [
    ("structure.prototype",                   "AFLOW prototype",     "warn"),
    ("structure.supercell",                   "Supercell",           "error"),
    ("structure.space_group.number",          "Space group number",  "error"),
    ("calculation.level.basis.cutoff_Ry",     "PW cutoff (Ry)",      "error"),
    ("calculation.level.basis.rho_cutoff_Ry", "Density cutoff (Ry)", "warn"),
    ("calculation.k_points.mesh",             "k-mesh",              "error"),
    ("calculation.level.spin",                "Spin treatment",      "error"),
    ("calculation.code.name",                 "Code name",           "error"),
    ("workflow.n_images",                     "NEB images",          "warn"),
    ("workflow.optimizer",                    "NEB optimizer",       "error"),
    ("workflow.k_spring_eV_per_A2",           "NEB spring k",        "warn"),
    ("workflow.fmax_eV_per_A",                "NEB fmax",            "warn"),
    ("workflow.prewrap",                      "IDPP prewrap",        "warn"),
]


def get_path(d: Any, path: str) -> Any:
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def normalize(v: Any) -> Any:
    """Coerce so 60 == 60.0 == "60" doesn't false-positive."""
    if isinstance(v, str):
        try:
            return float(v) if "." in v or "e" in v.lower() else int(v)
        except ValueError:
            return v.strip()
    if isinstance(v, list | tuple):
        return tuple(normalize(x) for x in v)
    return v


def values_equal(a: Any, b: Any) -> bool:
    a, b = normalize(a), normalize(b)
    if isinstance(a, int | float) and isinstance(b, int | float):
        return abs(float(a) - float(b)) < 1e-9
    return a == b


def lint_one(
    pilot_path: Path,
    *,
    strict: bool = False,
    repo_root: Path | None = None,
) -> bool:
    """Lint one pilot. Returns True on PASS or WARN-only, False on FAIL.

    ``repo_root`` resolves the ``paired_script`` path inside the pilot.
    Defaults to the pilot's own parent directory's parent (so a pilot at
    ``examples/pyr.tm.yaml`` resolves a paired script relative to the
    project root one level up). Override for non-standard layouts.
    """
    pilot_path = Path(pilot_path)
    if repo_root is None:
        repo_root = pilot_path.resolve().parent.parent

    pilot = yaml.safe_load(pilot_path.read_text(encoding="utf-8"))
    if not isinstance(pilot, dict):
        print(f"FAIL  {pilot_path.name}: not a YAML mapping")
        return False

    paired = (pilot.get("workflow") or {}).get("paired_script") or (
        pilot.get("structure") or {}
    ).get("paired_script")

    if not paired:
        print(f"SKIP  {pilot_path.name}: no paired_script — nothing to diff")
        return True

    script_path = repo_root / paired
    if not script_path.exists():
        print(f"FAIL  {pilot_path.name}: paired_script not found: {paired}")
        print("      [error] either pilot is synthetic or the script was renamed/moved")
        return False

    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            yaml_text, _inspector = extract_mod.extract(script_path)
        extracted = yaml.safe_load(yaml_text)
    except Exception as exc:
        print(f"FAIL  {pilot_path.name}: extractor crashed: {exc}")
        return False

    mismatches_err: list[tuple[str, str, Any, Any]] = []
    mismatches_warn: list[tuple[str, str, Any, Any]] = []
    matches = skipped = 0

    pilot_stage = get_path(pilot, "workflow.stage")

    for path, label, severity in DIFF_FIELDS:
        v_pilot = get_path(pilot, path)
        v_extr = get_path(extracted, path)
        if v_extr is None or v_pilot is None:
            skipped += 1
            continue

        # Stage-aware: smoke pilots use endpoint optimizer (BFGS), not NEB
        # optimizer (FIRE). The extractor reports FIRE because that is the
        # NEB-phase call in the same script.
        if (
            path == "workflow.optimizer"
            and pilot_stage == "smoke"
            and v_pilot in ("BFGS", "LBFGS", "LBFGSLineSearch", "MDMin")
        ):
            skipped += 1
            continue

        if values_equal(v_pilot, v_extr):
            matches += 1
        else:
            tup = (path, label, v_pilot, v_extr)
            (mismatches_err if severity == "error" else mismatches_warn).append(tup)

    has_err = bool(mismatches_err)
    has_warn = bool(mismatches_warn)
    verdict = "FAIL" if has_err or (strict and has_warn) else ("WARN" if has_warn else "PASS")

    print(f"{verdict}  {pilot_path.name}  → {paired}")
    print(
        f"    matched={matches}, mismatched_err={len(mismatches_err)}, "
        f"mismatched_warn={len(mismatches_warn)}, skipped={skipped}"
    )
    for path, label, v_pilot, v_extr in mismatches_err:
        print(f"    [error] {label} ({path})")
        print(f"            pilot:     {v_pilot!r}")
        print(f"            extracted: {v_extr!r}")
    for path, label, v_pilot, v_extr in mismatches_warn:
        print(f"    [warn]  {label} ({path})")
        print(f"            pilot:     {v_pilot!r}")
        print(f"            extracted: {v_extr!r}")
    return verdict != "FAIL"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tm-spec lint",
        description="Diff hand-crafted pilots against their paired_script Python files.",
    )
    parser.add_argument("paths", nargs="*", help="pilot YAML files")
    parser.add_argument(
        "--all",
        metavar="DIR",
        nargs="?",
        const="examples",
        help="lint every *.tm.yaml under DIR (default: 'examples/')",
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument(
        "--repo-root",
        default=None,
        help="resolve paired_script paths against this root (default: pilot's grandparent)",
    )
    args = parser.parse_args(argv)

    targets: list[Path] = []
    if args.all:
        d = Path(args.all)
        if not d.exists():
            parser.error(f"--all directory not found: {d}")
        targets.extend(sorted(d.glob("*.tm.yaml")))
    targets.extend(Path(p) for p in args.paths)

    if not targets:
        parser.error("provide pilot files or --all")

    repo_root = Path(args.repo_root) if args.repo_root else None

    n_pass = n_fail = 0
    for p in targets:
        if lint_one(p, strict=args.strict, repo_root=repo_root):
            n_pass += 1
        else:
            n_fail += 1
        print()

    print(f"Summary: {n_pass} pass, {n_fail} fail")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
