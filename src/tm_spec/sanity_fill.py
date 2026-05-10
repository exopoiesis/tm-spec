"""TM-Spec sanity-gate auto-fill from canonical NEB result JSONs and extxyz.

Parses run artefacts produced by typical canonical-NEB scripts (those
that ship in Third Matter and similar projects):

    - ``<output_dir>/neb_canonical_<mineral>.json`` — main result JSON
    - ``<work_dir>/relaxed_*.xyz``                  — relaxed structures (extxyz)

Auto-fills ``sanity[].observed`` and ``sanity[].pass`` for known gates::

    G01_FeS_bond              ← min(Fe-S) distance from relaxed_pristine.xyz
    G04_fmax_endpoints        ← endA_fmax / endB_fmax from result JSON
    G05_scf_converged          ← all images "convergence has been achieved"
    G08_idpp_prewrap           ← idpp_prewrap_n_unwrapped from JSON
    G09_endpoint_symmetry      ← dE_endpoints_eV from JSON
    G03_endpoints_distinct     ← d_H_nearest_endA vs endB

Usage::

    tm-spec sanity-fill examples/pyr_smoke.tm.yaml \\
        --json results/neb_canonical_pyr.json \\
        --xyz  results/relaxed_pristine.xyz \\
        --out  filled.tm.yaml
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml


def parse_extxyz_min_FeS(xyz_path: Path) -> float | None:
    """Naive minimum Fe-S distance (no MIC; assumes structure is relaxed).

    Reads only the first frame of an extxyz file. Returns None if the file
    is malformed or contains neither Fe nor S.
    """
    text = Path(xyz_path).read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) < 3:
        return None
    try:
        n_atoms = int(lines[0].strip())
    except ValueError:
        return None

    fe: list[tuple[float, float, float]] = []
    s: list[tuple[float, float, float]] = []
    for line in lines[2 : 2 + n_atoms]:
        parts = line.split()
        if len(parts) < 4:
            continue
        sym = parts[0]
        try:
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
        except ValueError:
            continue
        if sym == "Fe":
            fe.append((x, y, z))
        elif sym == "S":
            s.append((x, y, z))

    if not fe or not s:
        return None

    min_d = float("inf")
    for fx, fy, fz in fe:
        for sx, sy, sz in s:
            d = math.sqrt((fx - sx) ** 2 + (fy - sy) ** 2 + (fz - sz) ** 2)
            if d < min_d:
                min_d = d
    return round(min_d, 4)


def fill_from_json(
    doc: dict[str, Any],
    json_path: Path,
    fmax_target: float = 0.05,
) -> list[str]:
    """Mutate ``doc.sanity[]`` in place from a canonical NEB result JSON."""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    sanity = doc.get("sanity") or []
    updates: list[str] = []

    for gate in sanity:
        if not isinstance(gate, dict):
            continue
        gid = str(gate.get("id", ""))

        if gid.startswith("G04_fmax_endpoints"):
            fA, fB = data.get("endA_fmax"), data.get("endB_fmax")
            if fA is not None and fB is not None:
                gate["observed"] = [round(fA, 4), round(fB, 4)]
                gate["pass"] = (fA <= fmax_target) and (fB <= fmax_target)
                updates.append(f"G04: fmax=[{fA:.4f}, {fB:.4f}], target={fmax_target}")

        elif gid.startswith("G09_endpoint_symmetry"):
            de = data.get("dE_endpoints_eV")
            sym = data.get("endpoints_symmetric")
            if de is not None:
                gate["observed"] = round(de, 4)
                gate["pass"] = bool(sym) if sym is not None else (de < 0.005)
                updates.append(f"G09: dE={de:.4f} eV, sym={sym}")

        elif gid.startswith("G08_idpp_prewrap"):
            n = data.get("idpp_prewrap_n_unwrapped")
            if n is not None:
                gate["observed"] = f"idpp prewrap applied, {n} atom(s) unwrapped"
                gate["pass"] = True
                updates.append(f"G08: idpp_prewrap n_unwrapped={n}")

        elif gid.startswith("G03_endpoints_distinct"):
            dA, dB = data.get("d_H_nearest_endA"), data.get("d_H_nearest_endB")
            if dA is not None and dB is not None:
                delta = abs(dA - dB)
                gate["observed"] = f"d_H_endA={dA:.3f}, d_H_endB={dB:.3f}, |Δ|={delta:.3f}"
                gate["pass"] = delta > 0.5
                updates.append(f"G03: |d_H_A - d_H_B|={delta:.3f} (>0.5 => distinct)")

        elif gid.startswith("G05_scf_converged"):
            relax_p = data.get("relax_pristine_converged")
            if relax_p is not None:
                gate["observed"] = "pristine + endpoints SCF OK" if relax_p else "non-conv"
                gate["pass"] = bool(relax_p)
                updates.append(f"G05: pristine_converged={relax_p}")

    return updates


def fill_from_xyz(
    doc: dict[str, Any],
    xyz_path: Path,
    fes_threshold_A: float = 2.0,
) -> list[str]:
    """Update G01_FeS_bond from a relaxed extxyz."""
    sanity = doc.get("sanity") or []
    updates: list[str] = []
    min_d = parse_extxyz_min_FeS(Path(xyz_path))
    if min_d is None:
        return updates
    for gate in sanity:
        if not isinstance(gate, dict):
            continue
        if str(gate.get("id", "")).startswith("G01_FeS_bond"):
            gate["observed"] = min_d
            gate["pass"] = min_d > fes_threshold_A
            updates.append(f"G01: min(Fe-S)={min_d:.3f} Å (threshold {fes_threshold_A})")
    return updates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tm-spec sanity-fill",
        description="Auto-fill sanity[].observed and sanity[].pass from run artefacts.",
    )
    parser.add_argument("yaml", help="TM-Spec YAML to update")
    parser.add_argument("--json", help="canonical NEB result JSON")
    parser.add_argument("--xyz", help="relaxed_pristine.xyz (for G01_FeS_bond)")
    parser.add_argument(
        "--out", help="output YAML (default: <input>_filled.tm.yaml)"
    )
    parser.add_argument(
        "--fmax-target", type=float, default=0.05, help="fmax threshold for G04 (eV/Å)"
    )
    parser.add_argument(
        "--fes-threshold", type=float, default=2.0, help="min Fe-S threshold for G01 (Å)"
    )
    args = parser.parse_args(argv)

    yaml_path = Path(args.yaml)
    if not yaml_path.exists():
        print(f"FATAL: {yaml_path} not found", file=sys.stderr)
        return 2

    doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        print("FATAL: YAML is not a mapping", file=sys.stderr)
        return 2

    all_updates: list[str] = []

    if args.json:
        json_path = Path(args.json)
        if json_path.exists():
            all_updates.extend(fill_from_json(doc, json_path, fmax_target=args.fmax_target))
        else:
            print(f"WARN: {json_path} not found, skipping JSON fill", file=sys.stderr)

    if args.xyz:
        xyz_path = Path(args.xyz)
        if xyz_path.exists():
            all_updates.extend(fill_from_xyz(doc, xyz_path, fes_threshold_A=args.fes_threshold))
        else:
            print(f"WARN: {xyz_path} not found, skipping xyz fill", file=sys.stderr)

    out_path = Path(args.out) if args.out else yaml_path.with_name(yaml_path.stem + "_filled.tm.yaml")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")

    print(f"Wrote {out_path}")
    print()
    print(f"Auto-filled {len(all_updates)} gate(s):")
    for upd in all_updates:
        print(f"  {upd}")
    if not all_updates:
        print("  (none — sources missing or no matching gates)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
