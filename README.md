# TM-Spec

**Third Matter Specification** — declarative YAML/JSONL metalanguage for
DFT/MLIP/MD calculations on atomistic systems, with sanity gates,
provenance, and code-agnostic level-of-theory.

> Status: **v0.1 (draft)** · License: **MIT** (code) + **CC-BY-4.0** (spec) · Spec home: https://exopoiesis.github.io/tm-spec/

---

## What is it

One YAML file describes a structure, defects, magnetic state, environment,
reaction network, DFT/MLIP calculation, workflow (NEB / US / metaD / MD /
MLIP benchmark), results, **sanity gates**, and provenance — in a form
that:

- **Reviewers can read** in any text editor without runtime.
- **Validators can check** against a JSONSchema 2020-12 (`schemas/0.1.json`).
- **Tools can ingest**: extract from existing ASE/QE/CP2K/ABACUS Python
  scripts; export to NOMAD upload bundle; lint pilots vs paired scripts;
  auto-fill sanity gates from run artefacts.
- **Cross-codes**: same file describes a Quantum ESPRESSO, CP2K, ABACUS,
  GPAW, MACE, or CHGNet calculation — at the same level of detail,
  aligned with NOMAD Metainfo + OPTIMADE + QCSchema + magCIF + AFLOW +
  AiiDA + Antimony + PHREEQC.

### Why

Paper SI today is either code-specific dump (`pwscf.in`) or AiiDA archive
that requires AiiDA to inspect. TM-Spec is the missing middle: one
human-readable YAML file per calculation, validatable, exportable to
FAIR archives (NOMAD), and reproducible via paired-script lint. **Zero
runtime dependencies for inspection.**

### What is *not* the goal

- Replace AiiDA/atomate2 workflow management — they own provenance graph
  during work; TM-Spec owns the paper-grade snapshot.
- Be Turing-complete — no algorithms in YAML, only declarative state +
  pointer to a `paired_script`.

---

## Quickstart

```bash
pip install tm-spec       # PyPI release pending v0.3 tag

# validate one file
tm-spec validate examples/pyr_smoke.tm.yaml

# validate all bundled examples
tm-spec validate --all

# extract a stub from an ASE/QE/CP2K script
tm-spec extract path/to/neb_canonical.py --out tmp/stub.tm.yaml

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

Without install: `python -m tm_spec.<command> ...` after `pip install -e .`.

---

## A 30-second TM-Spec example

```yaml
spec: tm-spec/0.1
kind: NEBCalculation
id:   tm.pyr.vs.hint.smoke.2026-04-29

structure:
  formula:    Fe32S63H1
  prototype:  AB2_cP12_205_a_c       # AFLOW: pyrite cubic
  space_group: { number: 205, symbol: Pa-3 }
  cell:       { a: 5.418, c: 5.418 }
  supercell:  [2, 2, 2]
  pbc:        [true, true, true]

defects:
  reactions:
    - "S_S^× → V_S^••  + S(removed)"
    - "nil   → H_i^•   + e'"

magnetic:
  state: NM        # pyrite is diamagnetic

calculation:
  method: DFT
  level:
    xc:    PBE+D3(BJ)
    basis: { kind: plane_waves, cutoff_Ry: 60, rho_cutoff_Ry: 240 }
    smearing: { kind: gaussian, width_Ry: 0.005 }
    spin:  none
  k_points:    { mesh: [2, 2, 2] }
  convergence: { scf_Ry: 1.0e-8, fmax_eV_per_A: 0.05 }
  code: { name: QuantumESPRESSO, version: 7.3.1 }

workflow:
  kind:      NEB
  stage:     smoke
  endpoints:
    A: { ref: artifacts/endA.extxyz, E_eV: -128055.5404, fmax: 0.027 }
    B: { ref: artifacts/endB.extxyz, E_eV: -128055.5402, fmax: 0.026 }
  optimizer: BFGS
  prewrap:   idpp

results:
  status:         PASS
  paper_quotable: false
  notes: "Smoke endpoints, reused for production NEB v3."

sanity:
  - { id: G01_FeS_bond,        rule: "min(Fe-S) > 2.00 A", observed: 2.27, pass: true }
  - { id: G04_fmax_endpoints,  rule: "fmax(A,B) <= 0.05",  observed: [0.027, 0.026], pass: true }
  - { id: G09_endpoint_symmetry, rule: "|E_A - E_B| < 0.005 eV", observed: 0.0002, pass: true }

provenance:
  date:    2026-04-29
  author:  igor@exopoiesis.space
  parents: ["Q-115@2026-04-28"]
  compute: { host: vast-W3, gpu: A100, cost_usd: 4.0, walltime_h: 6.0 }
  hash:
    inputs:  sha256:placeholder_to_be_computed
    outputs: sha256:placeholder_to_be_computed
```

---

## Supported `kind`s

| kind | Required sections | Pilot |
|------|-------------------|-------|
| `NEBCalculation` | `workflow` (endpoints + n_images), `results` | `examples/pyr_smoke.tm.yaml`, `mack_vfe_neb.tm.yaml` |
| `USCalculation` | `cv_definition`, `sampling`, `pmf_analysis`, `results` | `examples/w2_us_pmf.tm.yaml` |
| `MetaDynCalculation` | `cv_definition`, `metadyn_protocol`, `fes_analysis`, `results` | `examples/w2_metad.tm.yaml` |
| `MDCalculation` | `md_protocol`, `results` (+ optional `trajectory_analysis`) | `examples/w1_grotthuss_aimd.tm.yaml` |
| `MLIPBenchmark` | `benchmark_setup`, `metrics`, `results` | `examples/w2_mlip_benchmark.tm.yaml` |
| `Structure`, `Defects`, `Magnetic`, `Environment`, `Reaction`, `SanityReport`, `Provenance` | (compositional fragments — JSONL streams) | (n/a — used in JSONL pipelines) |

---

## Repository layout

```
tm-spec/
├── README.md, SPECIFICATION.md, CHANGELOG.md, CITATION.cff
├── LICENSE              # MIT (code)
├── LICENSE-SPEC         # CC-BY-4.0 (specification text + schema)
├── pyproject.toml
├── schemas/
│   └── 0.1.json
├── docs/
│   ├── specification/v0.1.md
│   ├── design-decisions.md
│   ├── standards-alignment.md
│   ├── landscape.md
│   └── lit-review.md
├── examples/            # 6 real-world pilots (NEB, US, MetaD, MD, MLIP-bench)
├── src/tm_spec/         # validator, extract, lint, sanity_fill, exporters/
└── tests/               # pytest suite + fixtures
```

---

## Tests

The project ships an extensive pytest suite — see `tests/` and the
**Tests** section of [`docs/standards-alignment.md`](docs/standards-alignment.md).
Run locally:

```bash
pip install -e ".[dev]"
pytest -q
ruff check src tests
```

CI runs on Python 3.10, 3.11, 3.12 (see `.github/workflows/tests.yml`).

---

## Versioning

`tm-spec/<major>.<minor>` is part of each YAML document (`spec:` field).
Schema files are versioned in `schemas/<major>.<minor>.json`.
Breaking changes bump `<major>`; additive fields bump `<minor>`. Code
follows SemVer independently (`pyproject.toml`).

| Version | Status | Highlights |
|---------|--------|-----------|
| 0.1 | DRAFT | 11 kinds, 6 pilots, full toolchain (validator, extract, lint, sanity_fill, NOMAD export) |
| 0.2 | PLANNED | Recipe registry hooks (Q-TMSPEC-9), AiiDA bridge |
| 0.3 | HYPOTHESIS | Gillespie/COPASI kinds; QCSchema interop |

---

## How TM-Spec relates to other standards

Each TM-Spec section is borrowed from a mature domain standard (we do not
reinvent). See [`docs/standards-alignment.md`](docs/standards-alignment.md)
for the full mapping. Highlights:

- `structure` — AFLOW prototype + extxyz + CIF + OPTIMADE (lattice/pbc)
- `defects` — Kröger-Vink + pymatgen-defects / doped naming
- `magnetic` — magCIF + Bilbao MAGNDATA
- `environment` — PHREEQC v3 keyword blocks
- `reactions` — Antimony 3 / BNGL
- `calculation` — NOMAD Metainfo + LibXC + QCSchema
- `workflow` — AiiDA (parents/links) + atomate2 (Maker analogy)
- `results` — Materials Project / emmet schema
- `sanity` — **TM-Spec original** (compiled from project lessons-learned)
- `provenance` — AiiDA `provenance_graph` + git

---

## Citation

If TM-Spec helped your paper SI, please cite (see [`CITATION.cff`](CITATION.cff)):

> Morozov, I. (2026). *TM-Spec: a declarative YAML metalanguage for
> reproducible atomistic calculations.* Version 0.1.
> https://github.com/exopoiesis/tm-spec

---

## License

This project is dual-licensed using the [REUSE](https://reuse.software/) /
SPDX convention. Per-license texts live in [`LICENSES/`](LICENSES/):

- **Code** (`src/`, `tests/`, build files) — [MIT](LICENSES/MIT.txt).
- **Specification text & schema** (`docs/`, `schemas/`, `SPECIFICATION.md`) — [CC-BY-4.0](LICENSES/CC-BY-4.0.txt).

Root `LICENSE` is a copy of MIT (the primary code license, picked up by
GitHub's license detector). The dual-licensing pattern follows the
precedent of OPTIMADE, CFF, and SBML.

---

## Contact

Author: **Igor Morozov**, igor@exopoiesis.space ·
Issues: https://github.com/exopoiesis/tm-spec/issues
