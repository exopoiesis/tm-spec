# TM-Spec

**Third Matter Specification** — declarative YAML/JSONL metalanguage and
reference toolchain for DFT/MLIP/MD calculations on atomistic systems,
with sanity gates, provenance, NOMAD import/export, and code-agnostic
level-of-theory.

> Status: **v0.3 (draft)** · Package: **0.3.0** · License: **MIT** (code) +
> **CC-BY-4.0** (spec) · Spec home: https://exopoiesis.github.io/tm-spec/

---

## What is it

One YAML file describes a structure, defects, magnetic state,
environment, reaction network, DFT/MLIP calculation, workflow (NEB / US /
MetaD / MD / MLIP benchmark / single point / relaxation), results,
**sanity gates** (post-hoc) and an optional **pre-flight** block
(predictive), and provenance in a form that:

- **Reviewers can read** in any text editor without runtime.
- **Validators can check** against JSON Schema 2020-12
  (`schemas/0.3.json`; legacy `0.2` and `0.1` documents remain supported).
- **Tools can ingest**: extract from existing ASE/QE/CP2K/ABACUS Python
  scripts; import public NOMAD archive entries; export TM-Spec documents
  as a NOMAD upload bundle; lint pilots vs paired scripts; auto-fill
  sanity gates from run artefacts.
- **Cross-codes**: the same file describes Quantum ESPRESSO, CP2K,
  ABACUS, GPAW, MACE, CHGNet, or an imported NOMAD calculation at the
  same level of detail.

### Why

Paper SI today is often either a code-specific input dump (`pwscf.in`) or
a workflow archive that requires specialized runtime to inspect. TM-Spec
is the missing middle: one human-readable YAML file per calculation,
validatable, exportable to FAIR archives, and reproducible via paired
script lint. **Zero runtime dependencies for inspection.**

### What is not the goal

- Replace AiiDA/atomate2 workflow management. They own provenance graphs
  during work; TM-Spec owns the paper-grade snapshot.
- Be Turing-complete. YAML records declarative state and a pointer to a
  paired script or external archive entry.

---

## Quickstart

```bash
pip install tm-spec       # first PyPI release: v0.2.0

# validate one file
tm-spec validate examples/pyr_smoke.tm.yaml

# validate all bundled examples
tm-spec validate --all examples --strict

# extract a stub from an ASE/QE/CP2K script
tm-spec extract path/to/neb_canonical.py --out tmp/stub.tm.yaml

# import a public NOMAD archive entry (emits spec: tm-spec/0.3 with a
# G09_geometry_origin gate: dft_relaxed for relaxations, dft_static for
# single points, mlip_relaxed for ML methods; prodromos-ready out of the box)
tm-spec import-nomad <entry_id> --out imported.tm.yaml

# import structures from any OPTIMADE provider (Materials Project, NOMAD,
# OQMD, Alexandria). Structure-level only, so geometry_origin is honestly
# "unknown" and calculation is a minimal DFT stub.
tm-spec import-optimade --elements Fe S --provider mp --out fes.tm.yaml
tm-spec import-optimade --reduced-formula FeS2 --json

# import the COMPUTED magnetic ground state from Materials Project (the magnetic
# DEPTH that OPTIMADE/NOMAD lack): ordering + per-site magmoms -> magnetic block.
# Needs a (free) MP_API_KEY env var. AFM subtype unspecified by MP -> AFM-G + warning.
tm-spec import-mp --formula FeS2 --space-group 205 --out pyrite.tm.yaml
tm-spec import-mp --material-id mp-226 --json

# merge two TM-Spec docs locally (fill-only, same-material guarded): base
# depth (e.g. NOMAD method/results) is kept, overlay fills the holes (e.g.
# OPTIMADE formula variants + lattice_vectors).
tm-spec merge nomad.tm.yaml optimade.tm.yaml --out merged.tm.yaml

# one-shot: import OPTIMADE and merge each hit into a local NOMAD base
tm-spec import-optimade --reduced-formula FeS2 --merge nomad.tm.yaml --out merged.tm.yaml

# diff a hand-crafted pilot against its paired script
tm-spec lint examples/pyr_smoke.tm.yaml

# auto-fill sanity gates from run artefacts
tm-spec sanity-fill examples/pyr_smoke.tm.yaml \
    --json results/neb_canonical_pyr.json \
    --xyz  results/relaxed_pristine.xyz \
    --out  filled.tm.yaml

# build a NOMAD upload bundle
tm-spec export-nomad examples/*.tm.yaml --out nomad_upload.zip
```

Without install: `python -m tm_spec.cli ...` after `pip install -e .`.

---

## A 30-second TM-Spec example

```yaml
spec: tm-spec/0.2
kind: NEBCalculation
id: tm.pyr.vs.hint.smoke.2026-04-29
schema_url: https://exopoiesis.github.io/tm-spec/0.2.json

structure:
  formula: Fe32S63H1
  prototype: AB2_cP12_205_a_c
  space_group: { number: 205, symbol: Pa-3 }
  cell: { a: 5.418, c: 5.418 }
  supercell: [2, 2, 2]
  pbc: [true, true, true]

calculation:
  method: DFT
  level:
    xc: PBE+D3(BJ)
    basis: { kind: plane_waves, cutoff_Ry: 60, rho_cutoff_Ry: 240 }
    smearing: { kind: gaussian, width_Ry: 0.005 }
    spin: none
  k_points: { mesh: [2, 2, 2] }
  code: { name: QuantumESPRESSO, version: 7.3.1 }

workflow:
  kind: NEB
  stage: smoke
  endpoints:
    A: { ref: artifacts/endA.extxyz, E_eV: -128055.5404, fmax: 0.027 }
    B: { ref: artifacts/endB.extxyz, E_eV: -128055.5402, fmax: 0.026 }
  n_images: 7
  optimizer: BFGS
  prewrap: idpp

results:
  status: PASS
  paper_quotable: false

sanity:
  - { id: G01_FeS_bond, rule: "min(Fe-S) > 2.00 A", observed: 2.27, pass: true }
  - { id: G04_fmax_endpoints, rule: "fmax(A,B) <= 0.05", observed: [0.027, 0.026], pass: true }

provenance:
  date: 2026-04-29
  author: igor@exopoiesis.space
  parents: ["tm.pyr.vs.hint.pristine@2026-04-29"]
  compute: { host: cloud-gpu, gpu: A100, cost_usd: 4.0, walltime_h: 6.0 }
  hash:
    inputs: sha256:placeholder_to_be_computed
    outputs: sha256:placeholder_to_be_computed
```

---

## Supported kinds

| kind | Required sections | Pilot |
|------|-------------------|-------|
| `NEBCalculation` | `workflow`, `results` | `examples/pyr_smoke.tm.yaml`, `mack_vfe_neb.tm.yaml` |
| `USCalculation` | `cv_definition`, `sampling`, `pmf_analysis`, `results` | `examples/w2_us_pmf.tm.yaml` |
| `MetaDynCalculation` | `cv_definition`, `metadyn_protocol`, `fes_analysis`, `results` | `examples/w2_metad.tm.yaml` |
| `MDCalculation` | `md_protocol`, `results` | `examples/w1_grotthuss_aimd.tm.yaml` |
| `MLIPBenchmark` | `benchmark_setup`, `metrics`, `results` | `examples/w2_mlip_benchmark.tm.yaml` |
| `SinglePointCalculation` | `results` | `examples/nomad_pyrite_singlepoint.tm.yaml` |
| `RelaxCalculation` | `relax_protocol`, `results` | `examples/nomad_relax_example.tm.yaml` |
| `Structure`, `Defects`, `Magnetic`, `Environment`, `Reaction`, `SanityReport`, `Provenance` | compositional fragments for JSONL streams | n/a |

Optional sections (any kind):

| section | What it records | Pilot |
|---------|-----------------|-------|
| `preflight` | predictive pre-flight assessment from an external engine, BEFORE the run (counterpart of post-hoc `sanity`); shares the gate vocabulary in [`docs/gate-registry.md`](docs/gate-registry.md) | `examples/preflight_example.tm.yaml` |

---

## Repository layout

```text
tm-spec/
├── README.md, SPECIFICATION.md, CHANGELOG.md, CITATION.cff
├── LICENSE              # MIT (code)
├── LICENSES/            # MIT + CC-BY-4.0 texts
├── pyproject.toml
├── schemas/
│   ├── 0.1.json
│   ├── 0.2.json
│   └── 0.3.json
├── docs/
│   ├── specification/v0.1.md
│   ├── specification/v0.2.md
│   ├── specification/v0.3.md
│   ├── gate-registry.md
│   ├── design-decisions.md
│   ├── standards-alignment.md
│   ├── landscape.md
│   └── lit-review.md
├── examples/
├── src/tm_spec/
└── tests/
```

---

## Tests

```bash
pip install -e ".[dev]"
pytest -q
ruff check src tests
tm-spec validate --all examples --strict
```

CI runs on Python 3.10, 3.11, 3.12, and 3.13.

---

## Versioning

`tm-spec/<major>.<minor>` is part of each YAML document (`spec:` field).
Schema files are versioned in `schemas/<major>.<minor>.json`. Breaking
schema changes bump `<major>`; additive fields bump `<minor>`. Code
follows SemVer independently (`pyproject.toml`).

| Spec | Package | Status | Highlights |
|------|---------|--------|------------|
| 0.1 | 0.1.0 | DRAFT | Initial 11 kinds, 6 pilots, validator/extract/lint/sanity-fill/NOMAD export |
| 0.2 | 0.2.0 | DRAFT previous | NOMAD importer, `SinglePointCalculation`, `RelaxCalculation`, import provenance |
| 0.3 | 0.3.0 | DRAFT current | Optional `preflight` block (predictive) + `endpoint.geometry_origin` + shared gate registry |

---

## Citation

If TM-Spec helped your paper SI, cite:

> Morozov, I. (2026). *TM-Spec: a declarative YAML metalanguage for
> reproducible atomistic calculations.* Version 0.3.
> https://github.com/exopoiesis/tm-spec

---

## License

This project is dual-licensed using the REUSE/SPDX convention:

- **Code** (`src/`, `tests/`, build files) — [MIT](LICENSES/MIT.txt).
- **Specification text & schema** (`docs/`, `schemas/`, `SPECIFICATION.md`) —
  [CC-BY-4.0](LICENSES/CC-BY-4.0.txt).

Root `LICENSE` is a copy of MIT so GitHub detects the primary code
license.

---

## Contact

Author: **Igor Morozov**, igor@exopoiesis.space  
Issues: https://github.com/exopoiesis/tm-spec/issues
