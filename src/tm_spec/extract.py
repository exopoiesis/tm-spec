"""TM-Spec auto-extract — parse ASE/QE/CP2K/MACE Python script into a TM-Spec stub.

Strategy: AST-based static parsing (no script execution). Extracts:
    - argparse defaults (--ecutwfc, --kpts, --fmax-*, --n-images, --k-spring, ...)
    - crystal()/.repeat() calls → structure (cell, prototype, supercell, wyckoff)
    - Espresso()/CP2K()/Abacus()/MACECalculator()/CHGNet()/GPAW() calls → calculation level
    - NEB() + BFGS/FIRE/LBFGS → workflow + optimizer
    - input_data dict → spin, smearing, hubbard, mixing
    - paired_script → script's own path

Fields that need humans (marked ``[TODO_HUMAN]`` in output):
    - id, provenance (date/cost/walltime)
    - defects (semantic)
    - magnetic.state (heuristic from ``nspin`` only)
    - environment, reactions (semantic)
    - results, sanity (run-time data)

Usage::

    tm-spec extract path/to/neb_canonical.py [--out stub.tm.yaml] [--validate]
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Any

# AFLOW prototype label heuristics for known mineral spacegroups
PROTOTYPE_HINTS: dict[int, tuple[str, str]] = {
    205: ("AB2_cP12_205_a_c", "pyrite FeS2"),
    225: ("AB_cF8_225_a_b", "halite/B1"),
    129: ("AB_tP4_129_a_c", "mackinawite tetragonal P4/nmm"),
    194: ("A_hP2_194_c", "hcp/wurtzite-like"),
}


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _kwargs_to_dict(call_node: ast.Call) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kw in call_node.keywords:
        if kw.arg is None:
            continue
        val = _literal(kw.value)
        if val is None:
            try:
                val = ast.unparse(kw.value)
            except Exception:
                val = "<ast>"
        out[kw.arg] = val
    return out


def _positional_to_list(call_node: ast.Call) -> list[Any]:
    out = []
    for arg in call_node.args:
        lit = _literal(arg)
        if lit is None:
            try:
                lit = ast.unparse(arg)
            except Exception:
                lit = "<ast>"
        out.append(lit)
    return out


class ScriptInspector(ast.NodeVisitor):
    """Walk the AST of a Python script and collect facts useful for TM-Spec."""

    def __init__(self) -> None:
        self.argparse_defaults: dict[str, Any] = {}
        self.crystal_calls: list[dict[str, Any]] = []
        self.espresso_calls: list[dict[str, Any]] = []
        self.cp2k_calls: list[dict[str, Any]] = []
        self.abacus_calls: list[dict[str, Any]] = []
        self.gpaw_calls: list[dict[str, Any]] = []
        self.mace_calls: list[dict[str, Any]] = []
        self.chgnet_calls: list[dict[str, Any]] = []
        self.repeat_calls: list[list[Any]] = []
        self.builder_func_defaults: dict[str, dict[str, Any]] = {}
        self.neb_calls: list[dict[str, Any]] = []
        self.optimizer_calls: list[str] = []
        self.input_data_dict: Any = None
        self.has_idpp_prewrap_default_true: bool = False
        self.imports: set[str] = set()

    # ── visitors ──
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("build_"):
            fn_defaults: dict[str, Any] = {}
            args = node.args
            n_defaults = len(args.defaults)
            n_args = len(args.args)
            for i, default in enumerate(args.defaults):
                arg_idx = n_args - n_defaults + i
                arg_name = args.args[arg_idx].arg
                val = _literal(default)
                if val is not None:
                    fn_defaults[arg_name] = val
            self.builder_func_defaults[node.name] = fn_defaults
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for n in node.names:
            self.imports.add(n.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for n in node.names:
            self.imports.add(n.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr

        if name == "add_argument":
            self._visit_add_argument(node)
        elif name == "crystal":
            self.crystal_calls.append(
                {"args": _positional_to_list(node), "kwargs": _kwargs_to_dict(node)}
            )
        elif name == "Espresso":
            self.espresso_calls.append(_kwargs_to_dict(node))
            for kw in node.keywords:
                if kw.arg == "input_data":
                    val = _literal(kw.value)
                    if val is not None:
                        self.input_data_dict = val
        elif name in ("CP2KCalculator", "CP2K"):
            self.cp2k_calls.append(_kwargs_to_dict(node))
        elif name in ("Abacus", "ABACUS"):
            self.abacus_calls.append(_kwargs_to_dict(node))
        elif name == "GPAW":
            self.gpaw_calls.append(_kwargs_to_dict(node))
        elif name in ("MACECalculator", "mace_mp", "mace_off"):
            self.mace_calls.append({"name": name, "kwargs": _kwargs_to_dict(node)})
        elif name in ("CHGNetCalculator", "CHGNet"):
            self.chgnet_calls.append(_kwargs_to_dict(node))
        elif name == "repeat":
            self.repeat_calls.append(_positional_to_list(node))
        elif name == "NEB":
            self.neb_calls.append(_kwargs_to_dict(node))
        elif name in ("BFGS", "FIRE", "LBFGS", "LBFGSLineSearch", "MDMin"):
            self.optimizer_calls.append(name)

        self.generic_visit(node)

    def _visit_add_argument(self, call_node: ast.Call) -> None:
        if not call_node.args:
            return
        first = _literal(call_node.args[0])
        if not isinstance(first, str) or not first.startswith("--"):
            return
        flag = first.lstrip("-")
        kw = _kwargs_to_dict(call_node)
        if "default" in kw:
            self.argparse_defaults[flag] = kw["default"]
        elif kw.get("action") == "store_true":
            self.argparse_defaults[flag] = False
        elif kw.get("action") == "store_false":
            self.argparse_defaults[flag] = True

        if flag == "idpp-prewrap" and kw.get("default") is True:
            self.has_idpp_prewrap_default_true = True


def _scrape_input_data_fields(src_text: str) -> dict[str, Any]:
    """Regex fallback for fields inside ``input_data = {...}`` blocks.

    AST literal_eval fails when the dict has non-literal values
    (e.g. ``str(Path(...))``); we still want nspin / smearing / occupations.
    """
    out: dict[str, Any] = {}
    patterns = {
        "nspin": r'["\']nspin["\']\s*:\s*(\d+)',
        "occupations": r'["\']occupations["\']\s*:\s*["\'](\w+)["\']',
        "smearing": r'["\']smearing["\']\s*:\s*["\'](\w[\w\-]*)["\']',
        "degauss": r'["\']degauss["\']\s*:\s*([0-9.eE+\-]+)',
        "ecutwfc_input": r'["\']ecutwfc["\']\s*:\s*([\w.]+)',
        "ecutrho_input": r'["\']ecutrho["\']\s*:\s*([\w.]+)',
        "mixing_mode": r'["\']mixing_mode["\']\s*:\s*["\'](\w[\w\-]*)["\']',
        "conv_thr": r'["\']conv_thr["\']\s*:\s*([0-9.eE+\-]+)',
        "lda_plus_u": r'["\']lda_plus_u["\']\s*:\s*(True|False|\.true\.|\.false\.)',
        "starting_mag": r'["\']starting_magnetization\(\d+\)["\']\s*:\s*([0-9.eE+\-]+)',
        "Hubbard_U": r'["\']Hubbard_U\(\d+\)["\']\s*:\s*([0-9.eE+\-]+)',
    }
    for key, pat in patterns.items():
        m = re.search(pat, src_text)
        if m:
            v = m.group(1)
            try:
                if v.lower() in ("true", ".true."):
                    out[key] = True
                elif v.lower() in ("false", ".false."):
                    out[key] = False
                else:
                    out[key] = (
                        ast.literal_eval(v)
                        if v.replace(".", "")
                        .replace("-", "")
                        .replace("+", "")
                        .replace("e", "")
                        .replace("E", "")
                        .isdigit()
                        else v
                    )
            except Exception:
                out[key] = v
    return out


def _guess_mineral_tag(script_path: Path) -> str:
    name = script_path.stem.lower()
    for tag in (
        "pyr",
        "mack",
        "pent",
        "trog",
        "marc",
        "violar",
        "cubanit",
        "chalcopyrite",
        "bornite",
        "millerite",
        "grei",
        "smyth",
        "pyrrhot",
    ):
        if tag in name:
            return tag
    return "unknown"


def _safe_int_triple(supercell: Any) -> list[int] | None:
    try:
        return [int(supercell[0]), int(supercell[1]), int(supercell[2])]
    except (TypeError, ValueError, IndexError):
        return None


def _compute_formula(symbols: Any, sg: Any, supercell: Any) -> str | None:
    if not symbols:
        return None
    triple = _safe_int_triple(supercell)
    if triple is None:
        return None
    sx, sy, sz = triple
    if sg == 205 and len(symbols) == 2 and symbols == ["Fe", "S"]:
        n_fe = 4 * sx * sy * sz
        n_s = 8 * sx * sy * sz
        return f"{symbols[0]}{n_fe}{symbols[1]}{n_s}"
    if sg == 129 and len(symbols) == 2 and set(symbols) <= {"Fe", "S"}:
        n_fe = 2 * sx * sy * sz
        n_s = 2 * sx * sy * sz
        return f"Fe{n_fe}S{n_s}"
    return f"({'+'.join(symbols)} x {triple})"


def compose(script_path: Path, ins: ScriptInspector) -> str:
    """Return a YAML stub string for the given inspected script."""
    rel_script = str(script_path).replace("\\", "/")
    src_text = script_path.read_text(encoding="utf-8")
    scraped = _scrape_input_data_fields(src_text)
    mineral_tag = _guess_mineral_tag(script_path)

    if ins.neb_calls:
        kind = "NEBCalculation"
    elif "Espresso" in ins.imports or "CP2K" in ins.imports:
        kind = "MDCalculation"
    else:
        kind = "Structure"

    code_name: str | None = None
    if ins.espresso_calls or "Espresso" in ins.imports:
        code_name = "QuantumESPRESSO"
    elif ins.cp2k_calls or any("CP2K" in i for i in ins.imports):
        code_name = "CP2K"
    elif ins.abacus_calls:
        code_name = "ABACUS"
    elif ins.gpaw_calls or "GPAW" in ins.imports:
        code_name = "GPAW"
    elif ins.mace_calls:
        code_name = "MACE"
    elif ins.chgnet_calls:
        code_name = "CHGNet"

    if code_name in ("QuantumESPRESSO", "CP2K", "ABACUS", "GPAW"):
        method = "DFT"
    elif code_name in ("MACE", "CHGNet"):
        method = "MLIP"
    else:
        method = "[TODO_HUMAN]"

    structure_lines: list[str] = []
    if ins.crystal_calls:
        cc = ins.crystal_calls[0]
        kw = cc["kwargs"]
        symbols = kw.get("symbols")
        basis = kw.get("basis")
        sg = kw.get("spacegroup")
        cellpar = kw.get("cellpar")

        supercell: Any = ins.repeat_calls[0][0] if ins.repeat_calls else [1, 1, 1]
        if isinstance(supercell, tuple):
            supercell = list(supercell)
        if _safe_int_triple(supercell) is None:
            for defaults in ins.builder_func_defaults.values():
                if "repeat" in defaults:
                    supercell = list(defaults["repeat"])
                    break
            if _safe_int_triple(supercell) is None:
                supercell = [1, 1, 1]

        formula = _compute_formula(symbols, sg, supercell)
        proto_hint, proto_desc = PROTOTYPE_HINTS.get(sg, (None, None))

        structure_lines.append("structure:")
        if formula:
            structure_lines.append(f"  formula: {formula}             # [auto] from crystal() + repeat")
        if proto_hint:
            structure_lines.append(f"  prototype: {proto_hint}        # [auto] {proto_desc}")
        if sg:
            structure_lines.append(f"  space_group: {{ number: {sg} }}                # [auto]")
        if cellpar:
            a, b, c = cellpar[0], cellpar[1], cellpar[2]
            angles = cellpar[3:] if len(cellpar) >= 6 else None
            structure_lines.append("  cell:")
            structure_lines.append(f"    a: {a}  Å")
            structure_lines.append(f"    b: {b}  Å")
            structure_lines.append(f"    c: {c}  Å")
            if angles:
                structure_lines.append(f'    angles: "{list(angles)} deg"')
        if symbols and basis:
            structure_lines.append("  wyckoff:                                 # [auto, Wyckoff letters guessed]")
            for sym, pos in zip(symbols, basis, strict=False):
                structure_lines.append(f"    {sym}: {list(pos)}")
        triple = _safe_int_triple(supercell) or [1, 1, 1]
        source_note = (
            "from .repeat()"
            if ins.repeat_calls and _safe_int_triple(ins.repeat_calls[0][0])
            else "from build_*() default arg"
        )
        structure_lines.append(f"  supercell: {triple}                       # [auto] {source_note}")
        structure_lines.append("  pbc: [true, true, true]")
        structure_lines.append(f"  paired_script: {rel_script}")
    else:
        structure_lines.append(
            "structure:                                # [TODO_HUMAN] no crystal() found, manual build_*()?"
        )
        structure_lines.append("  formula: '[TODO_HUMAN]'")
        structure_lines.append("  pbc: [true, true, true]")

    nspin: Any = scraped.get("nspin")
    if nspin is None and ins.input_data_dict and isinstance(ins.input_data_dict, dict):
        sysblock = ins.input_data_dict.get("system", {})
        if isinstance(sysblock, dict):
            nspin = sysblock.get("nspin")

    if nspin == 1:
        spin = "none"
    elif nspin == 2:
        spin = "collinear"
    elif nspin == 4:
        spin = "non-collinear"
    else:
        spin = "none"

    magnetic_lines = ["", "magnetic:"]
    if nspin == 1:
        magnetic_lines.append("  state: NM                                  # [auto, nspin=1 in input_data]")
        magnetic_lines.append("  collinear: true")
        magnetic_lines.append("  magmoms_uB: {}")
        magnetic_lines.append("  surrogate_warning: null")
    elif nspin == 2:
        magnetic_lines.append("  state: AFM-G                              # [hint, nspin=2 — TODO_HUMAN: confirm]")
        magnetic_lines.append("  collinear: true")
        magnetic_lines.append("  magmoms_uB:                                # [TODO_HUMAN]")
        magnetic_lines.append("    Fe: 0.0")
        magnetic_lines.append('  surrogate_warning: "[TODO_HUMAN: PBE PM-itinerant proxy?]"')
    else:
        magnetic_lines.append("  state: NM                                  # [TODO_HUMAN: nspin not detected]")
        magnetic_lines.append("  collinear: true")
        magnetic_lines.append("  magmoms_uB: {}")

    cal_lines = ["", "calculation:"]
    cal_lines.append(f"  method: {method}")
    cal_lines.append("  level:")

    pseudo_dir = ins.argparse_defaults.get("pseudo-dir", "")
    if "oncv_pbe" in str(pseudo_dir).lower() or "pbe" in str(pseudo_dir).lower():
        cal_lines.append("    xc: PBE                                  # [hint] from pseudo dir name")
        cal_lines.append("    xc_libxc: [GGA_X_PBE, GGA_C_PBE]")
        cal_lines.append("    vdw: '[TODO_HUMAN: D2 | D3 | D3-BJ | none]'")
    else:
        cal_lines.append("    xc: '[TODO_HUMAN]'")

    if ins.espresso_calls:
        ecutwfc = ins.argparse_defaults.get("ecutwfc")
        ecutrho = ins.argparse_defaults.get("ecutrho")
        cal_lines.append(
            f"    basis: {{ kind: plane_waves, cutoff_Ry: {ecutwfc}, rho_cutoff_Ry: {ecutrho} }}"
        )
        if pseudo_dir:
            cal_lines.append(f"    pseudopotential: '[hint] {pseudo_dir}'  # [TODO_HUMAN refine]")
    elif ins.cp2k_calls:
        cal_lines.append("    basis: { kind: gaussians, family: GTH_MOLOPT }   # [hint, CP2K typical]")
        cal_lines.append("    pseudopotential: GTH-PBE")
    elif ins.abacus_calls:
        cal_lines.append("    basis: { kind: numeric_AOs }                       # [hint, ABACUS LCAO]")
    elif ins.mace_calls or ins.chgnet_calls:
        cal_lines.append("    type: ML_potential")

    # Smearing / occupations: prefer AST input_data dict, fall back to regex scrape
    # (the AST literal_eval fails as soon as the dict contains a non-literal value
    # like ``args.ecutwfc``, which is common in real scripts).
    sys_block: dict[str, Any] = {}
    if isinstance(ins.input_data_dict, dict):
        block = ins.input_data_dict.get("system", {})
        if isinstance(block, dict):
            sys_block = block

    smearing = (
        sys_block.get("smearing")
        or scraped.get("smearing")
        or ins.argparse_defaults.get("smearing")
    )
    degauss = (
        sys_block.get("degauss")
        or scraped.get("degauss")
        or ins.argparse_defaults.get("degauss")
    )
    occupations = (
        sys_block.get("occupations")
        or scraped.get("occupations")
        or ins.argparse_defaults.get("occupations")
    )
    if smearing or degauss:
        smearing_map = {
            "gaussian": "gaussian",
            "mp": "methfessel-paxton",
            "mv": "marzari-vanderbilt",
            "fd": "fermi",
        }
        sm = smearing_map.get(smearing, smearing)
        cal_lines.append(f"    smearing: {{ kind: {sm}, width_Ry: {degauss} }}")
    if occupations and occupations != "smearing":
        cal_lines.append(f"    # occupations: {occupations}")
    cal_lines.append(f"    spin: {spin}")

    kpts = ins.argparse_defaults.get("kpts")
    if kpts:
        cal_lines.append(f"  k_points: {{ mesh: {list(kpts)}, shift: [0, 0, 0] }}")

    conv_thr_e = ins.argparse_defaults.get("conv-thr-endpoint")
    fmax_e = ins.argparse_defaults.get("fmax-endpoint")
    fmax_n = ins.argparse_defaults.get("fmax-neb")
    if conv_thr_e or fmax_e or fmax_n:
        cal_lines.append("  convergence:")
        if conv_thr_e:
            cal_lines.append(f"    scf_Ry:        {conv_thr_e}")
        if fmax_n:
            cal_lines.append(f"    fmax_eV_per_A: {fmax_n}")

    cal_lines.append("  code:")
    cal_lines.append(f"    name: {code_name or '[TODO_HUMAN]'}")
    cal_lines.append("    version: '[TODO_HUMAN]'")
    cal_lines.append("    image:   '[TODO_HUMAN]'")
    if ins.espresso_calls:
        mpi = ins.argparse_defaults.get("mpi-np", 1)
        cal_lines.append(
            f'    mpirun: "mpirun --allow-run-as-root --bind-to none -np {mpi} pw.x"'
        )

    wf_lines: list[str] = []
    if kind == "NEBCalculation":
        n_images = ins.argparse_defaults.get("n-images")
        k_spring = ins.argparse_defaults.get("k-spring")
        neb_opt = "FIRE" if "FIRE" in ins.optimizer_calls else "BFGS"
        wf_lines.append("")
        wf_lines.append("workflow:")
        wf_lines.append("  kind: NEB")
        wf_lines.append("  stage: smoke                            # [TODO_HUMAN: smoke | production]")
        wf_lines.append("  endpoints:                              # [TODO_HUMAN] fill from run logs")
        wf_lines.append("    A: { ref: artifacts/endA.extxyz, E_eV: 0.0, fmax: 0.0 }")
        wf_lines.append("    B: { ref: artifacts/endB.extxyz, E_eV: 0.0, fmax: 0.0 }")
        if n_images:
            wf_lines.append(f"  n_images: {n_images}")
        wf_lines.append(f"  optimizer: {neb_opt}")
        if fmax_n:
            wf_lines.append(f"  fmax_eV_per_A: {fmax_n}")
        if k_spring:
            wf_lines.append(f"  k_spring_eV_per_A2: {k_spring}")
        if ins.has_idpp_prewrap_default_true:
            wf_lines.append("  prewrap: idpp                            # [auto] --idpp-prewrap default=True")
        wf_lines.append(f"  paired_script: {rel_script}")

    todo_lines = [
        "",
        "results:                                  # [TODO_HUMAN] fill from run logs",
        "  status: PRELIMINARY                      # [TODO_HUMAN: PASS | PRELIMINARY | FAIL | RETRACTED]",
        "  paper_quotable: false",
        "",
        "sanity:                                   # [TODO_HUMAN] add gates",
        '  - { id: G06_ascii_safe, rule: "no em-dash in script", pass: true }',
        "",
        "provenance:                               # [TODO_HUMAN] fill from run metadata",
        '  date: "2026-01-01"',
        "  author: igor@exopoiesis.space",
        "  parents: [stub_replace_me]",
        "  compute:",
        '    host: "TODO"',
        "    cost_usd: 0.0",
        "  hash:",
        "    inputs:  sha256:placeholder_to_be_computed",
        "    outputs: sha256:placeholder_to_be_computed",
    ]

    header = [
        f"# Auto-extracted from {rel_script}",
        "# Generator: tm_spec.extract (v0.1)",
        "# Fields marked [auto] = static AST extraction. [hint] = heuristic (verify).",
        "# Fields marked [TODO_HUMAN] = manual completion required (semantic / runtime).",
        "# Stub uses valid enum defaults so it passes schema; replace before paper.",
        "",
        "spec: tm-spec/0.1",
        f"kind: {kind}",
        f"id: tm.{mineral_tag}.todo.stub.2026-01-01      # [TODO_HUMAN: replace with real id]",
        "schema_url: https://exopoiesis.github.io/tm-spec/0.1.json",
        "",
    ]

    return "\n".join(header + structure_lines + magnetic_lines + cal_lines + wf_lines + todo_lines) + "\n"


def extract(script_path: Path) -> tuple[str, ScriptInspector]:
    """Parse a script and return ``(yaml_text, inspector)``.

    Convenience wrapper for programmatic use (lint, tests).
    """
    src = Path(script_path).read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(script_path))
    inspector = ScriptInspector()
    inspector.visit(tree)
    return compose(Path(script_path), inspector), inspector


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tm-spec extract",
        description="Extract a TM-Spec YAML stub from an ASE/QE/CP2K Python script.",
    )
    parser.add_argument("script", help="path to Python script")
    parser.add_argument("--out", help="output YAML path (default: <script_basename>.tm.yaml)")
    parser.add_argument(
        "--validate", action="store_true", help="run validator on the generated YAML"
    )
    args = parser.parse_args(argv)

    script_path = Path(args.script).resolve()
    if not script_path.exists():
        print(f"FATAL: {script_path} not found", file=sys.stderr)
        return 2

    yaml_text, ins = extract(script_path)

    out_path = Path(args.out) if args.out else Path(script_path.stem + ".tm.yaml")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml_text, encoding="utf-8")
    print(f"Wrote {out_path}")
    print()
    print("Extraction summary:")
    print(
        f"  imports: {sorted(ins.imports & {'Espresso', 'NEB', 'BFGS', 'FIRE', 'crystal', 'GPAW', 'CP2K', 'CP2KCalculator', 'MACECalculator', 'CHGNetCalculator'})}"
    )
    print(f"  argparse defaults: {len(ins.argparse_defaults)}")
    print(f"  crystal calls: {len(ins.crystal_calls)}")
    print(
        f"  Espresso: {len(ins.espresso_calls)}, CP2K: {len(ins.cp2k_calls)}, "
        f"ABACUS: {len(ins.abacus_calls)}, GPAW: {len(ins.gpaw_calls)}"
    )
    print(f"  MLIP: MACE={len(ins.mace_calls)}, CHGNet={len(ins.chgnet_calls)}")
    print(f"  NEB: {len(ins.neb_calls)}, optimizers: {set(ins.optimizer_calls)}")

    if args.validate:
        from . import validator as validator_mod

        print()
        print("Validating generated YAML...")
        return validator_mod.main([str(out_path), "--verbose"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
