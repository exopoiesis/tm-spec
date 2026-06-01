# Changelog

All notable changes to TM-Spec are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) for the reference
implementation. The specification version (`spec: tm-spec/<major>.<minor>` field)
is bumped independently — see `docs/specification/`.

## [Unreleased]

### Planned (v0.4+)
- Recipe registry hooks (`recipe:` block).
- Lotsman runtime integration (`Marina.execute(yaml, host)` round-trip).
- AiiDA bridge (`tm-spec → aiida-archive`).
- QCSchema interop layer.

## [0.3.0] — 2026-06-01

Additive bump introducing a predictive pre-flight layer alongside the
existing post-hoc sanity layer. Reference implementation tagged 0.3.0;
spec bumped to `tm-spec/0.3`. Existing 0.1/0.2 docs remain valid — the
validator selects schema by the doc's `spec:` field
(`SUPPORTED_VERSIONS = ("0.1", "0.2", "0.3")`).

### Specification (`spec: tm-spec/0.3`)
- New `endpoint.geometry_origin` field (under `workflow.endpoints.<label>`):
  `dft_relaxed | mlip_relaxed | experimental | as_built | unknown`.
  Energy comparisons across endpoints are valid only for `dft_relaxed`;
  an `mlip_relaxed` geometry can carry tens of eV of unrelaxed-lattice
  error even when local bond lengths look physical.
- New optional top-level `preflight` block — a predictive pre-flight
  assessment produced by an external engine (reference: Prodromos) BEFORE
  the expensive run. It is the forward-looking counterpart of the
  post-hoc `sanity` array and shares the same gate-ID vocabulary. Carries
  `engine`, `verdict`, `confidence`, `gates[]` (predictive gate
  evaluations with `p_success`), and `plan` (route mode `next_action`
  and/or tree mode scored `strategies[]` with cost / `p_success` /
  `cvar_usd` / `utility`). Optional; not part of any kind's required set.
- New shared gate registry at `docs/gate-registry.md` — canonical
  vocabulary for both `sanity[]` and `preflight.gates[]`.

### Reference implementation
- Validator: `SPEC_VERSION = "0.3"`, `SUPPORTED_VERSIONS = ("0.1", "0.2",
  "0.3")`. Schema auto-selection by `spec:` field unchanged.

### Examples
- `examples/preflight_example.tm.yaml` — NEBCalculation demonstrating
  `endpoint.geometry_origin: dft_relaxed` and an embedded `preflight` block.
- Existing 0.1/0.2 examples are left at their authored `spec:` versions
  (no semantic changes; v0.3 is a strict superset).

## [0.2.0] — 2026-05-10

Additive bump aimed at NOMAD ecosystem coverage and first PyPI release.
Reference implementation tagged 0.2.0; spec bumped to `tm-spec/0.2`.
Existing 0.1 docs remain valid — the validator selects schema by the
doc's `spec:` field (`SUPPORTED_VERSIONS = ("0.1", "0.2")`).

### Specification (`spec: tm-spec/0.2`)
- Two new `kind`s for direct NOMAD coverage:
  - `SinglePointCalculation` — single SCF (energy / forces / DOS / bands /
    gap / Bader). Dominant NOMAD entry shape.
  - `RelaxCalculation` — geometry optimisation (single trajectory).
    Distinct from `NEBCalculation` (multiple endpoints) and `MDCalculation`
    (time evolution).
- New schema sections (`$defs`):
  - `relax_protocol` — optimizer / fmax / max_steps / cell_relax.
  - `electronic_structure_analysis` — DOS / band_structure / band_gap_eV /
    charges / fermi_energy_eV / atomic magmoms.
  - `results_singlepoint`, `results_relax` — kind-specific results blocks.
- Provenance gains an optional `import_source` block (D-25) recording the
  external archive (NOMAD/MP/AFLOW), entry id, importer version, and the
  raw keys consulted (audit trail).
- Three new design decisions: D-23 (SinglePoint kind), D-24 (Relax kind),
  D-25 (NOMAD importer mapping convention).

### Reference implementation
- `tm_spec.importers.nomad` — bundled NOMAD entry → TM-Spec doc converter.
  Uses anonymous NOMAD Archive API. Cached fixtures in `tests/fixtures/nomad/`.
- New CLI sub-commands:
  - `tm-spec import-nomad <entry_id> [--out FILE]`
  - `tm-spec import-nomad-batch --query JSON --limit N --out-dir DIR/`
- Validator: `schema_path(version=)` and `load_schema(version=)` accept an
  explicit spec version; `validate_doc` auto-selects schema from the doc's
  `spec:` field. Public API gains `SUPPORTED_VERSIONS`.

### Examples
- `examples/nomad_pyrite_singlepoint.tm.yaml` — pyrite SCF (NOMAD-imported,
  PBE+D3, 96-atom supercell).
- `examples/nomad_relax_example.tm.yaml` — geometry optimisation imported
  from a public NOMAD entry.
- All six v0.1 examples bumped to `spec: tm-spec/0.2` (no semantic changes;
  v0.2 is a strict superset of v0.1).

### Release infrastructure
- `.github/workflows/release.yml` — OIDC trusted publishing to PyPI on
  `git tag v*`. One-time PyPI-side setup required (pending publisher with
  `owner=exopoiesis, repo=tm-spec, workflow=release.yml, env=pypi`).
- README adds PyPI install snippet and badge (activates after first
  successful release).

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

[Unreleased]: https://github.com/exopoiesis/tm-spec/compare/v0.3.0...HEAD
[0.3.0]:      https://github.com/exopoiesis/tm-spec/releases/tag/v0.3.0
[0.2.0]:      https://github.com/exopoiesis/tm-spec/releases/tag/v0.2.0
[0.1.0]:      https://github.com/exopoiesis/tm-spec/releases/tag/v0.1.0
