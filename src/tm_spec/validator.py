"""TM-Spec validator — JSONSchema 2020-12 + TM-Spec specific rules.

Schema location: bundled inside the package at
``src/tm_spec/schemas/0.1.json`` and loaded via
``importlib.resources``. The same file is mirrored at the repository
root as ``schemas/0.1.json``; ``test_schema_self.py`` keeps the
two in sync.

Rules enforced beyond the schema (per ``docs/design-decisions.md``):
    D-14 — ``results.paper_quotable`` MUST be a JSON boolean.
    D-15 — ``sanity[].pass`` MUST be one of ``true | false | "warn" | "skip"``.
    D-16 — ``provenance.compute.cost_usd`` MUST be numeric (no ``"~4"``).
    D-19 — ``MetaDynCalculation`` with ``status: PRELIMINARY`` SHOULD declare
           ``quote_constraint`` (warning, not error).

Plus structural sanity:
    - Sanity gate IDs are unique within a document.
    - ``provenance.parents`` entries look like IDs (string ≥ 4 chars).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

SPEC_VERSION = "0.1"
SCHEMA_FILENAME = f"{SPEC_VERSION}.json"


def schema_path() -> Path:
    """Return absolute filesystem path to the bundled schema.

    Uses ``importlib.resources.files`` so it works from an installed wheel
    (``pip install tm-spec``) as well as from a source checkout.
    """
    return Path(str(resources.files("tm_spec").joinpath("schemas", SCHEMA_FILENAME)))


def load_schema() -> dict[str, Any]:
    return json.loads(schema_path().read_text(encoding="utf-8"))


def _normalize(obj: Any) -> Any:
    """Recursively coerce datetime.date / datetime.datetime to ISO strings.

    PyYAML parses ``2026-04-30`` into ``datetime.date``; the schema's
    ``format: date`` requires a string. This is the only YAML→JSON
    impedance we paper over.
    """
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    if isinstance(obj, _dt.datetime | _dt.date):
        return obj.isoformat()
    return obj


def load_doc(path: Path) -> list[dict[str, Any]]:
    """Load YAML/JSONL/JSON. Returns a list (singleton for YAML/JSON)."""
    text = Path(path).read_text(encoding="utf-8")
    suffix = Path(path).suffix.lower()
    if suffix in {".yml", ".yaml"}:
        return [_normalize(yaml.safe_load(text))]
    if suffix in {".jsonl", ".ndjson"}:
        return [_normalize(json.loads(ln)) for ln in text.splitlines() if ln.strip()]
    if suffix == ".json":
        return [_normalize(json.loads(text))]
    raise ValueError(f"unsupported extension: {suffix}")


def tm_specific_rules(doc: dict[str, Any]) -> list[tuple[str, str]]:
    """Return list of ``(level, message)`` tuples beyond pure schema errors.

    ``level`` is ``"error"`` or ``"warn"``. The default CLI exits non-zero
    on any error; ``--strict`` also exits non-zero on warnings.
    """
    issues: list[tuple[str, str]] = []

    if not isinstance(doc, dict):
        issues.append(("error", "document is not a mapping/object"))
        return issues

    results = doc.get("results") or {}

    # D-14: paper_quotable must be boolean
    pq = results.get("paper_quotable")
    if pq is not None and not isinstance(pq, bool):
        issues.append((
            "error",
            f"D-14: results.paper_quotable must be boolean, got {type(pq).__name__} ({pq!r})",
        ))

    # D-16: cost_usd must be numeric
    cost = (doc.get("provenance") or {}).get("compute", {}).get("cost_usd")
    if cost is not None and not isinstance(cost, (int, float)):
        issues.append((
            "error",
            f"D-16: provenance.compute.cost_usd must be number, got {type(cost).__name__} ({cost!r})",
        ))

    # D-19: PRELIMINARY MetaDyn results should declare quote_constraint
    if (
        doc.get("kind") == "MetaDynCalculation"
        and results.get("status") == "PRELIMINARY"
        and not results.get("quote_constraint")
    ):
        issues.append((
            "warn",
            "D-19: PRELIMINARY MetaDyn result should declare quote_constraint "
            "(e.g. lower_bound_only)",
        ))

    # Sanity gate ID uniqueness
    sanity = doc.get("sanity") or []
    ids = [g.get("id") for g in sanity if isinstance(g, dict)]
    seen: set[str] = set()
    dupes: set[str] = set()
    for i in ids:
        if i in seen:
            dupes.add(i)
        seen.add(i)
    if dupes:
        issues.append(("error", f"duplicate sanity gate ids: {sorted(dupes)}"))

    # Provenance parents — string IDs of plausible length
    parents = (doc.get("provenance") or {}).get("parents") or []
    for p in parents:
        if not isinstance(p, str) or len(p) < 4:
            issues.append(("warn", f"provenance.parents entry suspicious: {p!r}"))

    # D-15 reinforcement: explicit pass-value enum check.
    # Note: ``1 == True`` and ``0 == False`` in Python, so a naive ``in`` test
    # would silently accept integers. Use isinstance(_, bool) to keep ints out.
    for g in sanity:
        if not isinstance(g, dict):
            continue
        passv = g.get("pass")
        if passv is None:
            # absence handled by JSON-Schema "required: pass"
            continue
        valid = isinstance(passv, bool) or passv in ("warn", "skip")
        if not valid:
            issues.append((
                "error",
                f"D-15: sanity gate {g.get('id', '?')} has invalid pass value {passv!r}",
            ))

    return issues


def _format_path(absolute_path) -> str:  # type: ignore[no-untyped-def]
    parts = [str(p) for p in absolute_path]
    return ".".join(parts) if parts else "<root>"


def validate_doc(
    doc: dict[str, Any],
    schema: dict[str, Any] | None = None,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Validate a single document. Returns ``(schema_errors, rule_issues)``.

    ``schema_errors`` is a list of ``(json_pointer, message)``.
    ``rule_issues`` is a list of ``(level, message)``.
    """
    if schema is None:
        schema = load_schema()
    validator = Draft202012Validator(schema)
    schema_errs = [
        (_format_path(err.absolute_path), err.message)
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    ]
    rule_issues = tm_specific_rules(doc)
    return schema_errs, rule_issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tm-spec validate",
        description="Validate TM-Spec YAML/JSONL artefacts against the bundled JSON Schema.",
    )
    parser.add_argument("paths", nargs="*", help="YAML/JSON/JSONL files to validate")
    parser.add_argument(
        "--all",
        metavar="DIR",
        nargs="?",
        const="examples",
        help="validate every *.tm.yaml under DIR (default: 'examples/')",
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="show kind/id even on PASS"
    )
    args = parser.parse_args(argv)

    targets: list[Path] = []
    if args.all:
        examples_dir = Path(args.all)
        if not examples_dir.exists():
            parser.error(f"--all directory not found: {examples_dir}")
        targets.extend(sorted(examples_dir.glob("*.tm.yaml")))
    targets.extend(Path(p) for p in args.paths)

    if not targets:
        parser.error("provide file paths or --all")

    if not schema_path().exists():
        print(f"FATAL: schema not found at {schema_path()}", file=sys.stderr)
        return 2

    schema = load_schema()
    n_pass = n_fail = n_warn = 0

    for path in targets:
        if not path.exists():
            print(f"FAIL  {path}: not found")
            n_fail += 1
            continue
        try:
            docs = load_doc(path)
        except Exception as exc:
            print(f"FAIL  {path}: parse error — {exc}")
            n_fail += 1
            continue

        for i, doc in enumerate(docs):
            tag = path.name + (f"[{i}]" if len(docs) > 1 else "")
            schema_errs, rule_issues = validate_doc(doc, schema)

            kind = (doc or {}).get("kind", "?") if isinstance(doc, dict) else "?"
            doc_id = (doc or {}).get("id", "?") if isinstance(doc, dict) else "?"

            has_errors = bool(schema_errs) or any(level == "error" for level, _ in rule_issues)
            has_warns = any(level == "warn" for level, _ in rule_issues)

            if not has_errors and not has_warns:
                if args.verbose:
                    print(f"PASS  {tag}  [{kind}]  {doc_id}")
                else:
                    print(f"PASS  {tag}  [{kind}]")
                n_pass += 1
                continue

            verdict = "FAIL" if has_errors or (args.strict and has_warns) else "WARN"
            print(f"{verdict}  {tag}  [{kind}]  {doc_id}")
            for loc, msg in schema_errs:
                print(f"    schema  {loc}: {msg}")
            for level, msg in rule_issues:
                marker = "[error]" if level == "error" else "[warn] "
                print(f"    rule    {marker} {msg}")

            if verdict == "FAIL":
                n_fail += 1
            else:
                n_warn += 1

    print()
    print(f"Summary: {n_pass} PASS, {n_warn} WARN, {n_fail} FAIL")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
