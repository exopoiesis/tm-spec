# Test suite

This suite is the change-detection layer for both the **specification**
(schema + examples) and the **reference implementation**
(`src/tm_spec/`). When you change anything in those areas, run
`pytest -q` first; if a test fails, the change is either a deliberate
breaking change (update CHANGELOG.md, bump versions) or a bug.

## Running

```bash
pip install -e ".[dev]"
pytest -q              # run everything
pytest -q tests/test_validator_rules.py       # one file
pytest -q -k "d15"     # tests matching a substring
```

CI runs the same commands on Python 3.10/3.11/3.12/3.13 — see
[`.github/workflows/tests.yml`](../.github/workflows/tests.yml).

## What each file covers

| File | Surface area | Why it matters |
|------|--------------|----------------|
| `test_schema_self.py`           | The JSON Schema itself | `Draft202012Validator.check_schema` + that the bundled copy matches the repo copy + that key enums (kind, status, pass_value) have not silently drifted. |
| `test_examples_validate.py`     | Every example in `examples/` | If a schema change breaks a real pilot, the test fails — forcing either a CHANGELOG entry (deliberate breaking change) or a revert. |
| `test_validator_rules.py`       | TM-Spec rules beyond schema | Each design decision (D-14, D-15, D-16, D-19) gets a positive AND a negative test. Tightening `pass` to reject `1`/`0` (Python's bool/int trap) is enforced here. |
| `test_extract.py`               | AST-based stub generator | Drives `extract.compose()` against a synthetic ASE/QE NEB script (`fixtures/scripts/fixture_neb_qe.py`). Catches regressions in argparse / `crystal()` / `Espresso(input_data=...)` parsing. |
| `test_lint.py`                  | Pilot ↔ paired-script diff | One in-sync fixture (PASS) + one drift fixture (FAIL on cutoff/k-mesh, WARN on n_images/k_spring). Strict-mode escalation tested. |
| `test_sanity_fill.py`           | Auto-fill of sanity gates | Drives G01 from `relaxed_*.xyz`, G03/G04/G05/G08/G09 from canonical NEB JSON, both happy and failure paths. |
| `test_nomad_export.py`          | NOMAD upload bundle | Verifies directory layout, manifest, ZIP integrity, dry-run mode, CLI dispatch. |
| `test_nomad_import.py`          | NOMAD archive importer | Converts cached NOMAD-shaped archive JSON into valid `SinglePointCalculation` and `RelaxCalculation` documents. |
| `test_versioning.py`            | Version consistency | Ensures `SPEC_VERSION` / `__version__` / `pyproject.toml` / `CITATION.cff` / schema `$id` / schema `const: tm-spec/X.Y` / `schemas/<name>.json` filename — all agree. |
| `test_cli.py`                   | `tm-spec` console script | help / version / unknown command / validate dispatch. |
| `test_load_doc.py`              | YAML/JSON/JSONL ingestion | Datetime normalisation, JSONL streaming, unknown-extension rejection. |

## Fixtures

`tests/fixtures/` ships:

- **scripts/** — synthetic Python scripts that look like real NEB/QE
  drivers but are never executed (only `ast.parse`-d). Two variants:
  one matches the bundled `fixture_neb_pilot.tm.yaml`, the other is a
  deliberate drift of cutoff / k-mesh / n_images / k_spring used by the
  lint tests.
- **xyz/** — extxyz files with controlled minimum Fe-S distances
  (above and below the G01 threshold).
- **neb_json/** — synthetic canonical-NEB result JSONs that drive the
  sanity-fill tests, with a "pass everything" file and a "fail
  everything" file.
- **nomad/** — cached NOMAD-shaped archive JSON fixtures for offline
  importer tests. They are intentionally small and synthetic enough to
  keep CI stable while preserving the source keys used by the importer.

## Conventions

- **Use the `minimal_neb_doc` fixture** when testing rule changes that
  do not need a specific real-world structure. It is the smallest doc
  that PASSes the validator — pytest deepcopies it on each call so
  mutations in one test do not leak to another.
- **Absolute paths** come from the `repo_root` / `examples_dir` /
  `fixtures_dir` / `schemas_dir` fixtures so tests run from any cwd.
- **No network access**: every test must run offline. The NOMAD export
  tests build local ZIPs and verify their contents; they never touch
  `nomad-lab.eu`.
- **Filter warnings as errors** (`pyproject.toml` → `filterwarnings`).
  If a test emits a `DeprecationWarning`, it is a failing test.

## Adding a new test

1. Decide where it belongs (above table). Prefer extending an existing
   file over creating a new one if the surface area matches.
2. If you need a new fixture, add it under `tests/fixtures/<category>/`
   and document its purpose in this README.
3. If the test exercises a design decision, reference the decision ID
   (D-XX) in the test name so future readers can trace it back to
   `docs/design-decisions.md`.

## When a test fails

- Read the failure carefully — the assertion messages are written so
  the fix is obvious.
- If the test is right and the code is wrong → fix the code.
- If the test is wrong because of a deliberate spec change → update
  the test, update `CHANGELOG.md`, bump `SPEC_VERSION` if the change
  is breaking.
- Never silently weaken an assertion. If a check used to be tight and
  is now loose, the diff has to explain why.
