"""TM-Spec → NOMAD upload bundle exporter.

Builds a ZIP archive ready for NOMAD upload
(https://nomad-lab.eu/prod/v1/gui/user/uploads). Each TM-Spec YAML
becomes one entry directory containing:

    - ``tm_spec.yaml``  — source-of-truth (NOMAD will index as auxiliary)
    - ``README.md``     — auto-generated human summary
    - ``raw/``          — copied raw QE/CP2K/ABACUS inputs+outputs

The top-level archive contains ``nomad.yaml`` with upload metadata
(coauthors, references, datasets).

Usage::

    tm-spec export-nomad examples/*.tm.yaml \\
        --out tmp/nomad_upload.zip \\
        --raw-root ../results/dft_datasets/ \\
        --comment "TM-Spec example bundle"
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# TM-Spec → NOMAD Metainfo mapping (per docs/standards-alignment.md §1)
NOMAD_HINTS_BY_CODE: dict[str, dict[str, Any]] = {
    "QuantumESPRESSO": {
        "raw_glob": ["*.in", "*.out", "*.xml", "*.upf", "neb.dat", "neb.path", "*.xyz"],
        "parser": "parser/quantumespresso",
    },
    "CP2K": {
        "raw_glob": ["*.inp", "*.out", "*.restart", "*.ener", "*HILLS*", "*COLVAR*", "*.xyz"],
        "parser": "parser/cp2k",
    },
    "ABACUS": {
        "raw_glob": ["INPUT", "STRU", "KPT", "running_*.log", "OUT.*"],
        "parser": "parser/abacus",
    },
    "GPAW": {
        "raw_glob": ["*.gpw", "*.txt", "*.out"],
        "parser": "parser/gpaw",
    },
    "MACE": {
        "raw_glob": ["*.xyz", "*.json", "*.log"],
        "parser": "(no NOMAD parser; auxiliary files only)",
    },
    "CHGNet": {
        "raw_glob": ["*.xyz", "*.json", "*.log"],
        "parser": "(no NOMAD parser; auxiliary files only)",
    },
}


def load_tm_spec(path: Path) -> Any:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def render_readme(doc: dict[str, Any], source_path: str) -> str:
    """Per-entry README.md (human-readable summary)."""
    kind = doc.get("kind", "?")
    doc_id = doc.get("id", "?")
    structure = doc.get("structure", {})
    formula = structure.get("formula") or structure.get("composition", "?")
    prototype = structure.get("prototype", "?")
    sg = structure.get("space_group", {}).get("number", "?")
    supercell = structure.get("supercell", "?")
    state = doc.get("magnetic", {}).get("state", "?")
    calculation = doc.get("calculation", {})
    method = calculation.get("method", "?")
    code = calculation.get("code", {}).get("name", "?")
    code_version = calculation.get("code", {}).get("version", "?")
    level = calculation.get("level", {})
    results = doc.get("results", {})
    status = results.get("status", "?")
    paper_quotable = results.get("paper_quotable", False)
    provenance = doc.get("provenance", {})
    date_str = provenance.get("date", "?")
    cost = provenance.get("compute", {}).get("cost_usd", "?")
    sanity = doc.get("sanity") or []
    n_pass = sum(1 for g in sanity if g.get("pass") is True)
    n_warn = sum(1 for g in sanity if g.get("pass") == "warn")
    n_skip = sum(1 for g in sanity if g.get("pass") == "skip")
    n_fail = sum(1 for g in sanity if g.get("pass") is False)

    lines = [
        f"# {doc_id}",
        "",
        f"**Kind:** {kind} | **Status:** {status} | **Paper-quotable:** {paper_quotable}",
        "",
        "## Structure",
        f"- Formula: `{formula}`",
        f"- Prototype: `{prototype}` (space group {sg})",
        f"- Supercell: `{supercell}`",
        f"- Magnetic state: `{state}`",
        "",
        "## Method",
        f"- Method: **{method}**",
        f"- Code: **{code}** (version: `{code_version}`)",
    ]
    if level:
        for key, label in [
            ("xc", "XC functional"),
            ("xc_libxc", "LibXC"),
            ("vdw", "vdW correction"),
            ("basis", "Basis"),
            ("smearing", "Smearing"),
            ("hubbard", "Hubbard"),
            ("spin", "Spin"),
        ]:
            if level.get(key):
                lines.append(f"- {label}: `{level[key]}`")
    kpts = calculation.get("k_points")
    if kpts:
        lines.append(f"- k-mesh: `{kpts}`")
    lines.extend([
        "",
        "## Sanity gates",
        f"- {n_pass} PASS, {n_warn} WARN, {n_skip} SKIP, {n_fail} FAIL",
    ])
    if n_fail:
        lines.append("- ⚠ Failures:")
        for g in sanity:
            if g.get("pass") is False:
                lines.append(
                    f"  - `{g.get('id')}` — {g.get('rule', '')} (observed: {g.get('observed', '?')})"
                )
    lines.extend([
        "",
        "## Provenance",
        f"- Date: {date_str}",
        f"- Compute cost: USD {cost}",
    ])
    if provenance.get("parents"):
        lines.append(f"- Parents: {', '.join(provenance['parents'])}")
    if provenance.get("decisions"):
        lines.append(f"- Decisions: {', '.join(provenance['decisions'])}")
    if provenance.get("literature"):
        lines.append(f"- Literature: {', '.join(provenance['literature'])}")
    lines.extend([
        "",
        f"_Source: `{source_path}`. Auto-generated by `tm-spec export-nomad`._",
    ])
    return "\n".join(lines) + "\n"


def render_nomad_metadata(
    comment: str,
    references: list[str],
    coauthors: list[str],
    dataset_name: str,
) -> str:
    meta = {
        "comment": comment,
        "references": references,
        "coauthors": coauthors,
        "datasets": [dataset_name] if dataset_name else [],
        "external_id": f"tm-spec-{date.today().isoformat()}",
    }
    return yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)


def find_raw_dir(doc: dict[str, Any], raw_root: Path | None) -> Path | None:
    """Locate raw outputs directory for this entry, by date+mineral heuristic."""
    if not raw_root or not raw_root.exists():
        return None

    doc_id = doc.get("id", "")
    parts = doc_id.split(".")
    iso = parts[-1] if parts and len(parts[-1]) == 10 else None
    mineral = parts[1] if len(parts) > 1 else None

    if iso:
        candidate = raw_root / iso
        if candidate.exists():
            for sub in candidate.iterdir():
                if sub.is_dir() and (mineral is None or mineral in sub.name.lower()):
                    return sub

    return None


def copy_raw_files(raw_dir: Path | None, dest_dir: Path, code_name: str | None) -> int:
    if not raw_dir or not raw_dir.exists():
        return 0

    hint = NOMAD_HINTS_BY_CODE.get(code_name or "", {})
    globs = hint.get("raw_glob", ["*"])

    raw_dest = dest_dir / "raw"
    raw_dest.mkdir(parents=True, exist_ok=True)

    n = 0
    for pattern in globs:
        for src in raw_dir.rglob(pattern):
            if src.is_file():
                rel = src.relative_to(raw_dir)
                dst = raw_dest / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                n += 1
    return n


def build_bundle(
    spec_paths: list[Path],
    bundle_dir: Path,
    raw_root: Path | None,
    *,
    comment: str,
    references: list[str],
    coauthors: list[str],
    dataset_name: str,
) -> list[dict[str, Any]]:
    bundle_dir.mkdir(parents=True, exist_ok=True)

    (bundle_dir / "nomad.yaml").write_text(
        render_nomad_metadata(comment, references, coauthors, dataset_name),
        encoding="utf-8",
    )

    top_readme_lines = [
        f"# TM-Spec — NOMAD upload bundle ({date.today().isoformat()})",
        "",
        comment,
        "",
        f"## Entries ({len(spec_paths)})",
        "",
    ]
    summary_per_entry: list[dict[str, Any]] = []

    for spec_path in spec_paths:
        doc = load_tm_spec(spec_path)
        if not isinstance(doc, dict):
            print(f"SKIP {spec_path}: not a mapping", file=sys.stderr)
            continue

        doc_id = doc.get("id", spec_path.stem)
        safe_id = doc_id.replace("/", "_").replace(":", "_")
        entry_dir = bundle_dir / safe_id
        entry_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(spec_path, entry_dir / "tm_spec.yaml")
        (entry_dir / "README.md").write_text(
            render_readme(doc, spec_path.name), encoding="utf-8"
        )

        calc = doc.get("calculation", {})
        code_name = calc.get("code", {}).get("name")
        if not code_name and calc.get("backends"):
            code_name = calc["backends"][0].get("name")
        raw_dir = find_raw_dir(doc, raw_root) if raw_root else None
        n_raw = copy_raw_files(raw_dir, entry_dir, code_name) if raw_dir else 0

        kind = doc.get("kind", "?")
        status = doc.get("results", {}).get("status", "?")
        if raw_dir:
            top_readme_lines.append(
                f"- **{safe_id}** [{kind}, {status}] — {n_raw} raw files | raw dir: `{raw_dir}`"
            )
        else:
            top_readme_lines.append(f"- **{safe_id}** [{kind}, {status}] — no raw dir found")

        summary_per_entry.append({
            "id": doc_id,
            "kind": kind,
            "status": status,
            "code": code_name,
            "n_raw_files": n_raw,
            "raw_dir": str(raw_dir) if raw_dir else None,
        })

    top_readme_lines.extend([
        "",
        "## NOMAD upload",
        "1. Login at https://nomad-lab.eu/prod/v1/gui/user/uploads",
        "2. Click **Create a new upload**",
        "3. Drag this ZIP (or upload tarball)",
        "4. NOMAD parsers auto-process raw files (QE/CP2K/ABACUS recognised)",
        "5. After processing, edit metadata if needed; publish to obtain DOI",
        "",
        "## Mapping notes",
        "TM-Spec → NOMAD Metainfo mapping per docs/standards-alignment.md §1.",
        "Raw outputs in `<entry>/raw/` are auto-parsed; `tm_spec.yaml` is auxiliary metadata.",
    ])
    (bundle_dir / "README.md").write_text(
        "\n".join(top_readme_lines) + "\n", encoding="utf-8"
    )

    (bundle_dir / "manifest.json").write_text(
        json.dumps(
            {"entries": summary_per_entry, "generated": date.today().isoformat()},
            indent=2,
        ),
        encoding="utf-8",
    )
    return summary_per_entry


def zip_bundle(bundle_dir: Path, zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in bundle_dir.rglob("*"):
            if path.is_file():
                arcname = path.relative_to(bundle_dir.parent)
                zf.write(path, arcname=str(arcname))
    return zip_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tm-spec export-nomad",
        description="Build a NOMAD upload bundle (ZIP) from TM-Spec YAML files.",
    )
    parser.add_argument("specs", nargs="+", help="TM-Spec YAML files to bundle")
    parser.add_argument("--out", required=True, help="output ZIP path or bundle dir (with --dry-run)")
    parser.add_argument(
        "--raw-root",
        default=None,
        help="root containing raw outputs (date subdirs). Optional.",
    )
    parser.add_argument(
        "--comment",
        default="TM-Spec export bundle",
        help="upload comment (NOMAD shows in metadata)",
    )
    parser.add_argument("--reference", action="append", default=[], help="reference URL/DOI (repeat)")
    parser.add_argument(
        "--coauthor",
        action="append",
        default=None,
        help="coauthor email (repeat). Default: ['igor@exopoiesis.space']",
    )
    parser.add_argument("--dataset", default="tm-spec-bundle", help="NOMAD dataset name")
    parser.add_argument("--dry-run", action="store_true", help="build directory tree only, no ZIP")
    args = parser.parse_args(argv)

    spec_paths = [Path(s) for s in args.specs]
    missing = [p for p in spec_paths if not p.exists()]
    if missing:
        print(f"FATAL: missing files: {missing}", file=sys.stderr)
        return 2

    out = Path(args.out)
    raw_root = Path(args.raw_root).resolve() if args.raw_root else None
    coauthors = args.coauthor if args.coauthor else ["igor@exopoiesis.space"]

    bundle_dir = (
        out
        if args.dry_run
        else (out.with_suffix("") if out.suffix == ".zip" else (out.parent / (out.stem + "_bundle")))
    )

    summary = build_bundle(
        spec_paths,
        bundle_dir,
        raw_root,
        comment=args.comment,
        references=args.reference,
        coauthors=coauthors,
        dataset_name=args.dataset,
    )

    if not args.dry_run:
        zip_path = zip_bundle(bundle_dir, out)
        print(f"Bundle dir: {bundle_dir}")
        print(f"ZIP:        {zip_path}")
    else:
        print(f"Bundle dir (dry-run): {bundle_dir}")

    print()
    print("Entry summary:")
    for s in summary:
        marker = "✓" if s["n_raw_files"] > 0 else "(no raw)"
        print(f"  {marker} {s['id']} [{s['kind']}] — code={s['code']}, raw_files={s['n_raw_files']}")

    print()
    n_with_raw = sum(1 for s in summary if s["n_raw_files"] > 0)
    print(f"Total: {len(summary)} entries, {n_with_raw} with raw outputs.")
    if n_with_raw < len(summary) and raw_root:
        print(
            f"Note: entries without raw will upload as auxiliary-only metadata. "
            f"Check that `{raw_root}` contains date subdirs matching TM-Spec ids."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
