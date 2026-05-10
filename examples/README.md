# Example TM-Spec documents

Eight pilot artefacts. Six are real Third Matter calculations; two are
NOMAD-shaped imported examples used to exercise v0.2 ecosystem coverage.
Every example PASSes both JSON Schema validation and TM-Spec rule checks.

| File | `kind` | System | Method / code | Status | Cost (USD) |
|------|--------|--------|---------------|--------|------------|
| [`pyr_smoke.tm.yaml`](pyr_smoke.tm.yaml) | NEBCalculation | pyrite Fe32S63H1 (V_S + H_i, 96 atoms) | DFT (PBE+D3, QE 7.3.1, smoke / endpoints only) | PASS | 4 |
| [`mack_vfe_neb.tm.yaml`](mack_vfe_neb.tm.yaml) | NEBCalculation | mackinawite Fe35S36H2 (V_Fe + 2H_int, 73 atoms) | DFT (PBE+D3, QE 7.3.1, FIRE NEB, n=9) | PASS | 47 |
| [`w2_us_pmf.tm.yaml`](w2_us_pmf.tm.yaml) | USCalculation | mack 3x3x1 + 12 H2O + H+ | MLIP (MACE-MP-0 + CHGNet, umbrella sampling) | PASS | 0 |
| [`w2_metad.tm.yaml`](w2_metad.tm.yaml) | MetaDynCalculation | mack 3x3x1 + 12 H2O + H+ | DFT-MD (CP2K, well-tempered MetaD) | PRELIMINARY | 181 |
| [`w1_grotthuss_aimd.tm.yaml`](w1_grotthuss_aimd.tm.yaml) | MDCalculation | mack 3x3x1 + 12 H2O + H+ | AIMD (CP2K, plain NVT) | PRELIMINARY | 60 |
| [`w2_mlip_benchmark.tm.yaml`](w2_mlip_benchmark.tm.yaml) | MLIPBenchmark | MACE-MP-0 vs CHGNet vs DFT-MetaD (mack PMF) | cross-method comparison | PASS | cumulative |
| [`nomad_pyrite_singlepoint.tm.yaml`](nomad_pyrite_singlepoint.tm.yaml) | SinglePointCalculation | pyrite Fe32S64 | NOMAD-imported DFT single point | PRELIMINARY | 0 |
| [`nomad_relax_example.tm.yaml`](nomad_relax_example.tm.yaml) | RelaxCalculation | Si2 | NOMAD-imported DFT relaxation | PRELIMINARY | 0 |

## Running validation

```bash
tm-spec validate --all examples --strict
tm-spec validate examples/mack_vfe_neb.tm.yaml --verbose
```

## Lint against paired scripts

The `paired_script:` field in NEB pilots points to the Python script that
actually produced the artefact. `tm-spec lint` runs the AST extractor on
that script and diffs against the pilot to catch hand-written drift
(wrong cutoff, wrong k-mesh, wrong optimizer, wrong number of NEB images,
etc.).

Paths in the real Third Matter examples point into the original project;
in a standalone clone, provide your own paired scripts for linting.

## Why these examples?

- `pyr_smoke` — NM material, `nspin=1`, no Hubbard U, smoke stage.
- `mack_vfe_neb` — production NEB with paper-quotable barrier.
- `w2_us_pmf` — MLIP method, two backends, umbrella windows + WHAM.
- `w2_metad` — well-tempered MetaD with lower-bound quote constraint.
- `w1_grotthuss_aimd` — plain MD with trajectory analysis.
- `w2_mlip_benchmark` — cross-method comparison.
- `nomad_pyrite_singlepoint` — v0.2 single-SCF import shape.
- `nomad_relax_example` — v0.2 geometry-optimisation import shape.
