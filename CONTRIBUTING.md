# Contributing to TM-Spec

TM-Spec is a small spec + reference implementation. Contributions are
welcome — issues, discussions, and PRs. The project is intended to
mature slowly; "small, well-tested, well-documented" beats "fast, big,
incomplete".

## Workflow

1. **Open an issue first** for non-trivial changes (new `kind`, new
   sanity gate, breaking schema field). Drive-by typo fixes can go
   straight to PR.
2. **Branch** from `main`.
3. **Run the test suite locally** before pushing:

   ```bash
   pip install -e ".[dev]"
   ruff check src tests
   pytest -q
   tm-spec validate --all examples --strict
   ```

4. **Update CHANGELOG.md** under `[Unreleased]`.
5. **Open a PR.** CI runs ruff + pytest on Python 3.10–3.13.

## Spec changes

The specification text lives in `docs/specification/v<N>.<M>.md` and
its JSONSchema in `schemas/<N>.<M>.json`.

- **Additive changes** (new optional field, new enum entry that does
  not invalidate existing examples) → bump `<minor>` in the schema and
  `SPEC_VERSION`.
- **Breaking changes** (new `required:`, removed field, renamed enum)
  → bump `<major>`. Keep the previous schema file so old documents
  still validate against their declared `spec:` version.
- **Decisions log.** Every non-trivial change MUST add a `D-NN` entry
  to `docs/design-decisions.md` with: the decision, the source (paper,
  upstream tool, prior conversation), and a `Breaking?` flag.

## Reference-implementation changes

Code under `src/tm_spec/` follows independent SemVer (`pyproject.toml`).
Bump `<patch>` for bug fixes, `<minor>` for new CLI subcommands or
library helpers, `<major>` for any change that breaks an existing
public API surface listed in `tm_spec/__init__.py::__all__`.

## Adding a new `kind`

1. Update `schemas/<N>.<M>.json`:
   - Add the kind to `$defs.kind.enum`.
   - Add an `if/then` branch in `allOf` requiring its sections.
   - Add new `$defs/<section>` entries.
2. Add a pilot to `examples/<name>.tm.yaml`. Real data only — no
   schema-stub-only examples.
3. Add a parametrized entry to `tests/test_examples_validate.py`.
4. Document the `kind` in `docs/specification/v<N>.<M>.md` and
   `README.md`'s "Supported kinds" table.
5. Add or extend a `D-NN` decision in `docs/design-decisions.md`.

## Adding a new sanity gate

1. Pick the next free `G<NN>` ID (current max: G24).
2. Document the gate in `docs/specification/v<N>.<M>.md` under §9
   (sanity).
3. If the gate can be auto-filled from artefacts, add a handler to
   `src/tm_spec/sanity_fill.py` and a test in
   `tests/test_sanity_fill.py`.

## Style

- `ruff` settings live in `pyproject.toml` — use them.
- Default to **no comments** unless they explain *why*. Code says what.
- Prefer **dataclasses or plain dicts** over custom classes for spec
  payloads; we are not building an ORM.
- Identifier names follow the spec where it matters (`paper_quotable`,
  `quote_constraint`); Pythonic everywhere else.

## Code of Conduct

Be kind. Disagree with the technical content, not the person.
