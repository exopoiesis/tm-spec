# Example TM-Spec documents

Six pilot artefacts from real Third Matter calculations. Each one
PASSes both the JSONSchema validator and the TM-Spec rule checker, and
serves as a canonical demonstration of one supported `kind`.

| File | `kind` | System | Method / code | Status | Cost (USD) |
|------|--------|--------|---------------|--------|------------|
| [`pyr_smoke.tm.yaml`](pyr_smoke.tm.yaml)         | NEBCalculation       | pyrite Fe32S63H1 (V_S + H_i, 96 atoms)         | DFT (PBE+D3, QE 7.3.1, smoke / endpoints only) | PASS         | 4   |
| [`mack_vfe_neb.tm.yaml`](mack_vfe_neb.tm.yaml)   | NEBCalculation       | mackinawite Fe16S18H2 (V_Fe + H_int, 136 atoms) | DFT (PBE+D3, QE 7.3.1, FIRE NEB, n=9)          | PASS         | 47  |
| [`w2_us_pmf.tm.yaml`](w2_us_pmf.tm.yaml)         | USCalculation        | mack 3×3×1 + 12 H₂O + H⁺                        | MLIP (MACE-MP-0 + CHGNet, umbrella sampling)   | PASS         | 0   |
| [`w2_metad.tm.yaml`](w2_metad.tm.yaml)           | MetaDynCalculation   | mack 3×3×1 + 12 H₂O + H⁺                        | DFT-MD (CP2K, well-tempered MetaD)             | PRELIMINARY  | 181 |
| [`w1_grotthuss_aimd.tm.yaml`](w1_grotthuss_aimd.tm.yaml) | MDCalculation | mack 3×3×1 + 12 H₂O + H⁺                        | AIMD (CP2K, plain NVT)                          | RUNNING      | (TBD) |
| [`w2_mlip_benchmark.tm.yaml`](w2_mlip_benchmark.tm.yaml) | MLIPBenchmark | MACE-MP-0 vs CHGNet vs DFT-MetaD (mack PMF)     | cross-method comparison                         | PASS         | (cumulative) |

## Running validation

```bash
# every example must pass
tm-spec validate --all

# or one-by-one
tm-spec validate examples/mack_vfe_neb.tm.yaml --verbose
```

## Lint against paired scripts

The `paired_script:` field in each pilot points to the Python script that
actually produced the artefact. `tm-spec lint` runs the AST extractor on
that script and diffs against the pilot to catch hand-written drift
(wrong cutoff, wrong k-mesh, wrong optimizer, wrong number of NEB
images, etc.). Note: the paths point into the original Third Matter
repository; in a standalone clone of `tm-spec` the lint step requires
the user to provide their own scripts.

## Why these six?

Each pilot stresses a different region of the schema, exercising
polymorphism (`allOf` + `if/then`), required-section enforcement, and
the original sanity-gate layer:

- `pyr_smoke` — NM material, `nspin=1`, no Hubbard U, smoke stage.
- `mack_vfe_neb` — itinerant magnetic surrogate, full NEB production.
- `w2_us_pmf` — MLIP method, `backends[]`, umbrella windows + WHAM.
- `w2_metad` — well-tempered MetaD with wall correction, demonstrates
  `paper_quotable: true` paired with `quote_constraint: lower_bound_only`.
- `w1_grotthuss_aimd` — plain MD with `trajectory_analysis` (msd, rdf,
  hbond_lifetime, grotthuss_hops).
- `w2_mlip_benchmark` — cross-method comparison, no single calculation
  (results aggregate across backends).
