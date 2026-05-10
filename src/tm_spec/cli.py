"""Single ``tm-spec`` console script: dispatcher for sub-commands.

Examples::

    tm-spec validate examples/pyr_smoke.tm.yaml
    tm-spec validate --all examples/
    tm-spec extract path/to/script.py --out stub.tm.yaml
    tm-spec lint examples/pyr_smoke.tm.yaml
    tm-spec sanity-fill in.tm.yaml --json result.json --xyz relaxed.xyz --out filled.tm.yaml
    tm-spec export-nomad examples/*.tm.yaml --out bundle.zip
    tm-spec import-nomad <entry_id> --out my_corpus/<id>.tm.yaml
    tm-spec import-nomad-batch --query '{"results.method.method_name":"DFT"}' \
        --limit 25 --out-dir my_corpus/
    tm-spec version
"""
from __future__ import annotations

import sys

from . import __version__

SUBCOMMANDS = {
    "validate":           "tm_spec.validator:main",
    "extract":            "tm_spec.extract:main",
    "lint":               "tm_spec.lint:main",
    "sanity-fill":        "tm_spec.sanity_fill:main",
    "export-nomad":       "tm_spec.exporters.nomad:main",
    "import-nomad":       "tm_spec.importers.nomad:main",
    "import-nomad-batch": "tm_spec.importers.nomad:main_batch",
}


def _resolve(target: str):  # type: ignore[no-untyped-def]
    module_path, _, attr = target.partition(":")
    mod = __import__(module_path, fromlist=[attr])
    return getattr(mod, attr)


def _print_help() -> None:
    print("Usage: tm-spec <command> [options]")
    print()
    print("Commands:")
    for name in SUBCOMMANDS:
        print(f"  {name}")
    print("  version")
    print()
    print("Run 'tm-spec <command> --help' for command-specific options.")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv

    if not args or args[0] in {"-h", "--help", "help"}:
        _print_help()
        return 0

    if args[0] in {"-V", "--version", "version"}:
        print(f"tm-spec {__version__}")
        return 0

    cmd, rest = args[0], args[1:]
    if cmd not in SUBCOMMANDS:
        print(f"unknown command: {cmd!r}", file=sys.stderr)
        _print_help()
        return 2

    fn = _resolve(SUBCOMMANDS[cmd])
    return int(fn(rest) or 0)


if __name__ == "__main__":
    sys.exit(main())
