# Changelog

All notable changes to TM-Spec are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) for the reference
implementation. The specification version (`spec: tm-spec/<major>.<minor>` field)
is bumped independently — see `docs/specification/`.

## [Unreleased]

### Planned (v0.2)
- Recipe registry hooks (`recipe:` block) — per Q-TMSPEC-9.
- AiiDA bridge (`tm-spec → aiida-archive`).
- QCSchema interop layer.

## [0.1.0] — 2026-05-10

Initial public release. Specification frozen as draft v0.1; reference
implementation tagged 0.1.0.

### Specification (`spec: tm-spec/0.1`)
- 11 supported `kind`s: `Structure`, `Defects`, `Magnetic`, `Environment`,
  `Reaction`, `NEBCalculation`, `USCalculation`, `MetaDynCalculation`,
  `MDCalculation`, `MLIPBenchmark`, `SanityReport`, `Provenance`.
- 22 design decisions recorded (D-01..D-22) — see `docs/design-decisions.md`.
- Alignment with 11 parent standards: NOMAD Metainfo, OPTIMADE 1.3,
  QCSchema, magCIF, AFLOW prototype, AiiDA provenance, Antimony 3,
  PHREEQC v3, pymatgen-defects, doped, MACE/CHGNet — see
  `docs/standards-alignment.md`.
- 24 sanity gates compiled (G01..G24).

### Reference implementation (`src/tm_spec/`)
- `validator.py` — JSONSchema 2020-12 + TM-Spec rules (D-14/D-15/D-16/D-19).
- `extract.py` — AST-based stub generator from ASE/QE/CP2K/MACE Python
  scripts (no script execution).
- `lint.py` — diff hand-crafted pilot vs auto-extracted from `paired_script`
  (stage-aware: smoke ↔ production).
- `sanity_fill.py` — auto-fill `sanity[].observed`/`pass` from
  `relaxed_*.xyz` and canonical NEB result JSON.
- `exporters/nomad.py` — NOMAD upload bundle (ZIP) with per-entry
  `tm_spec.yaml` + `README.md` + `raw/` and top-level `nomad.yaml`.

### Examples
- `examples/pyr_smoke.tm.yaml` — pyrite V_S+H_i NEB smoke (s128, $4, PASS).
- `examples/mack_vfe_neb.tm.yaml` — mackinawite V_Fe+H_i NEB production
  (s133, $47, PASS, paper-quotable).
- `examples/w2_us_pmf.tm.yaml` — mackinawite umbrella sampling PMF
  (MACE+CHGNet apples-to-apples, s136, PASS).
- `examples/w2_metad.tm.yaml` — mackinawite well-tempered MetaD CP2K
  (s121-s136, $181, PRELIMINARY/lower_bound_only).
- `examples/w1_grotthuss_aimd.tm.yaml` — mackinawite + 12 H₂O AIMD
  (s107-s136 RUNNING).
- `examples/w2_mlip_benchmark.tm.yaml` — MACE-MP-0 vs CHGNet vs DFT
  cross-validation (s136, T6 deliverable).

### Licensing

- Dual-licensed via [REUSE](https://reuse.software/) / SPDX convention:
  reference implementation under MIT, specification text + JSON Schema
  under CC-BY-4.0. Per-license canonical texts in `LICENSES/`.

### Tests
- `tests/test_schema_self.py` — schema is itself a valid JSONSchema.
- `tests/test_examples_validate.py` — every bundled example PASSes
  validator (no schema/rule errors).
- `tests/test_validator_rules.py` — explicit unit tests for D-14
  (paper_quotable bool), D-15 (sanity pass enum), D-16 (cost_usd
  numeric), D-19 (PRELIMINARY MetaD ⇒ quote_constraint).
- `tests/test_extract.py` — AST extractor on a bundled fixture script
  produces a stub that PASSes the validator.
- `tests/test_lint.py` — lint detects deliberate cutoff/k-mesh/optimizer
  drift between a pilot and a paired script.
- `tests/test_sanity_fill.py` — gates G01/G04/G09 auto-fill from xyz +
  JSON fixtures.
- `tests/test_nomad_export.py` — NOMAD bundle produces a valid ZIP
  with expected directory structure.
- `tests/test_versioning.py` — `spec` field matches `schemas/` filename.

[Unreleased]: https://github.com/exopoiesis/tm-spec/compare/v0.1.0...HEAD
[0.1.0]:      https://github.com/exopoiesis/tm-spec/releases/tag/v0.1.0
