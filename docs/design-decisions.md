# TM-Spec — Decision Log

> Auditable log of TM-Spec design decisions. Each decision references an
> authoritative source (or explicitly marks original semantics).
>
> Format: `D-NN | <date> | Decision | Source | Breaking?`

---

## v0.1 → v0.2 alignment (2026-05-09, after STANDARDS_ALIGNMENT.md)

### D-01 | 2026-05-09 | Smearing kind: lowercase enum
- **Decision:** `Marzari-Vanderbilt` → `marzari-vanderbilt`. Also `gaussian`, `fermi`, `methfessel-paxton`, `tetrahedra` — all lowercase.
- **Source:** NOMAD Metainfo `Run.method.smearing.kind` convention [CLAIM, runschema plugin].
- **Breaking:** YES — legacy names will fail schema validation. Applied before publishing v0.1.

### D-02 | 2026-05-09 | Basis kind: `plane_waves` primary, `PW` alias
- **Decision:** `basis.kind: plane_waves` (NOMAD primary); aliases allowed: `PW`, `pw`.
- **Source:** NOMAD Metainfo `Run.method.basis_set` enum.
- **Breaking:** YES in strict mode, but aliases provide backward compatibility.

### D-03 | 2026-05-09 | XC functional: human + LibXC dual
- **Decision:** keep `xc: PBE+D3(BJ)` (human-readable primary); add optional machine fields:
  - `xc_libxc: [GGA_X_PBE, GGA_C_PBE]`
  - `vdw: D3-BJ`
- **Source:** NOMAD/LibXC convention.
- **Breaking:** NO (new optional fields).

### D-04 | 2026-05-09 | OPTIMADE structure interop layer
- **Decision:** keep human a/b/c/α/β/γ + `pbc: [bool,bool,bool]`. Add optional computed fields:
  - `lattice_vectors_A: [[ax,ay,az],...]` (Cartesian Å)
  - `dimension_types: [0|1, 0|1, 0|1]`
  - `chemical_formula_descriptive`, `_reduced`, `_anonymous`
- **Source:** OPTIMADE 1.3.0 [FACT for 1.2.0, CLAIM for 1.3.0].
- **Breaking:** NO.

### D-05 | 2026-05-09 | Wyckoff vs cartesian_site_positions
- **Decision:** keep `wyckoff: {Fe@2a: [...]}` (human, science-readable). On export, expand to `species_at_sites` + `cartesian_site_positions`.
- **Source:** OPTIMADE [FACT] has no native Wyckoff; AFLOW prototype label carries letters but not coordinates. Our expanded form is original.
- **Breaking:** NO.

### D-06 | 2026-05-09 | Defects: keep Kröger-Vink + add machine layer
- **Decision:** retain `defects.reactions[]: "Fe_Fe^× → V_Fe'' + ..."` as primary (human). Add **machine layer**:
  ```yaml
  defects:
    objects:
      - { name: v_Fe,  kind: vacancy,      site: ..., charge: -2, multiplicity: 1 }
      - { name: H_i,   kind: interstitial, site: ..., charge: +1, multiplicity: 2 }
  ```
- **Source:** pymatgen-analysis-defects v2026.3.20 + doped v3.1.0 — naming convention `v_Fe`, `H_i`, `Cu_Zn` [FACT].
- **Breaking:** NO.

### D-07 | 2026-05-09 | Magnetic: keep AFM-G shortcut + add BNS optional
- **Decision:** keep `magnetic.state: AFM-G | AFM-A | AFM-C | FM | ferri | NM | PM-itinerant`. Add optional `magnetic.bns_group: "P_b 4'/n m m'"` for magCIF export.
- **Source:** magCIF dictionary v0.9.8 — BNS magnetic space group [FACT]. Our AFM-G shortcut is original human-friendly semantics.
- **Breaking:** NO.

### D-08 | 2026-05-09 | Environment T: keep K + computed C
- **Decision:** primary `T: 363.15 K`. Optional computed `temp_C: 90` for PHREEQC export.
- **Source:** PHREEQC v3 `temp` keyword = °C [FACT, USGS docs verified].
- **Breaking:** NO.

### D-09 | 2026-05-09 | Environment redox: keep Eh + auto-derive pe
- **Decision:** primary `redox.Eh: -0.40 V_SHE`. Optional `redox.pe_derived: -6.8` (computed via Nernst).
- **Source:** PHREEQC uses `pe`, but Eh is more natural for electrochemistry.
- **Breaking:** NO.

### D-10 | 2026-05-09 | Environment composition: PHREEQC element-valence verbatim
- **Decision:** `composition_molal: { Fe(2): 1.0e-3, S(-2): 5.0e-4 }` — exact match of PHREEQC element-valence notation. Default unit = `mol/kgw` (PHREEQC default), explicitly encoded via `_molal` suffix.
- **Source:** PHREEQC v3 SOLUTION block [FACT].
- **Breaking:** NO — our format is already correct.

### D-11 | 2026-05-09 | Reactions: Unicode primary + ASCII alias for export
- **Decision:** keep Unicode arrows + Kröger-Vink in `reactions[].rule` (human). Export tooling spec `tm-spec → antimony`:
  - `→` → `->`, `⇌` → `<->`
  - `H_aq^+` → `H_aq`, `(H–Fe)_Fe^×` → `H_Fe_x`
  - `[X]` → `X`, `θ` → `theta_`
- **Source:** Antimony 3.x — ASCII identifiers only [FACT, libantimony grammar].
- **Breaking:** NO.

### D-12 | 2026-05-09 | Provenance parents: human IDs + AiiDA lookup
- **Decision:** keep human-readable parent IDs (`tm.mack.vfe.hint.smoke@2026-05-03`). On export → AiiDA UUID + LinkType enum (`INPUT_CALC`, `INPUT_WORK`, `CALL_WORK`, ...).
- **Source:** AiiDA 2.7.3 LinkType [FACT].
- **Breaking:** NO.

### D-13 | 2026-05-09 | Status enum: keep richer 4-value
- **Decision:** keep `status: PASS | PRELIMINARY | FAIL | RETRACTED`. emmet `state: successful/unsuccessful/error` — partial mapping on export.
- **Source:** original TM-Spec semantics. PRELIMINARY and RETRACTED are not covered by emmet.
- **Breaking:** NO.

### D-14 | 2026-05-09 | `paper_quotable: bool` + `quote_constraint` extension
- **Decision:** keep `paper_quotable: bool` as a first-class field. **Refinement (D-19 follow-up):** for partial cases (lower bound, upper bound) add a separate optional field `quote_constraint: lower_bound_only | upper_bound_only | point_estimate | range_only`. This keeps `paper_quotable` a clean boolean and adds an orthogonal dimension "how exactly to cite".
- **Source:** our chemist+physicist opus QA pipeline + W2 metad pilot (LB-only result).
- **Breaking:** NO.

### D-15 | 2026-05-09 | Sanity gates: 4-value pass enum
- **Decision:** `sanity[].pass: true | false | "warn" | "skip"`.
  - `true/false` — gate passed successfully / failed.
  - `"warn"` — gate flagged an anomaly that is not blocking (W2 US T_drift, WHAM convergence).
  - `"skip"` — gate not applicable to this kind (W2 US does not check AFM because MLIP does not enforce magmom).
- **Source:** original TM-Spec semantics, observed in W2 US pilot.
- **Breaking:** NO.

### D-16 | 2026-05-09 | Cost format: structured object
- **Decision:** `provenance.compute.cost_usd: { value: 47.30, approx: false }` or simply `47.30` for exact values; `~4` (string) — deprecated. Schema requires a number.
- **Source:** consistency.
- **Breaking:** YES — pilot pyr_smoke has `cost_usd: ~4`; fix to `cost_usd: 4.0`.

### D-17 | 2026-05-09 | MLIP backend schema (for kind: USCalculation, MLIPBenchmark)
- **Decision:** when `calculation.method: MLIP`, use `backends[]` array (not `level`):
  ```yaml
  backends:
    - { name: MACE-MP-0, variant: medium, version: 0.3.13, foundation: true, fine_tuned: false }
    - { name: CHGNet,    variant: v0.3.0, foundation: true, fine_tuned: false }
  ```
- **Source:** MACE foundation_models.py + CHGNet model.py variant naming [FACT].
- **Breaking:** NO (W2 US pilot already uses backends[]).

---

## Kind conventions (Q-TMSPEC-1, closed 2026-05-09)

### D-18 | 2026-05-09 | One sampling family = one kind
- **Decision:** each enhanced-sampling method family gets its own kind:
  - `NEBCalculation` — endpoints + path + Ea
  - `USCalculation` — windows + WHAM + PMF
  - `MetaDynCalculation` — hills + FES + bias_factor (implemented in D-19)
  - `MDCalculation` — plain MD without bias (v0.2)
  - `MLIPBenchmark` — multi-method comparison (v0.2)
- **Source:** constructive decision, based on structural differences (endpoints vs windows vs hills vs trajectory).
- **Breaking:** NO.

---

## v0.2 extension — MetaDynCalculation (2026-05-10)

### D-19 | 2026-05-10 | MetaDynCalculation kind with three new sections
- **Decision:** new `kind: MetaDynCalculation` with three required sections:
  1. **`cv_definition`** — reused from USCalculation (same CV semantics).
  2. **`metadyn_protocol`** (NEW) — variant (well_tempered/standard/tigersaw/frequency_adaptive), hill (height + width + freq), bias_factor (γ + effective_dT), wall (type/position/k), monitoring (3-phase from CP2K_METADYN_RESTART_MONITORING).
  3. **`fes_analysis`** (NEW) — FES reconstruction method (WT_reweighting / direct_integration / Tiwary_Parrinello / WHAM), grid (with bounds + coverage flag), wall_correction (for post-hoc math fix), convergence (target + achieved boolean).
  4. Results: new `$defs/results_metad` with `delta_F_dagger_eV: object` (multiple estimates: apparent / extended_grid / wall_corrected_LB / extrapolated_2sigma) + `cross_validation_eV` (vs other methods) + `quote_constraint` (D-14 extension).
- **Source:** Barducci 2008 WT-MetaD canonical, knowledge/W2_DEBUG_ANALYSIS_2026-05-01.md, knowledge/CP2K_METADYN_RESTART_MONITORING.md, our s130 math audit.
- **Breaking:** NO (new kind, added alongside existing kinds).
- **New sanity gates from w2_metad pilot:**
  - `G17_grid_coverage` — FES grid covers CV_max + 3σ (bug #1 catcher)
  - `G18_wall_position` — wall.position > max(initial_CV) (bug #2 catcher)
  - `G19_wt_convergence` — block window analysis target
  - `G20_no_grotthuss_exchange` — CV(tracked_H) stays > threshold (CV proxy validity)
  - `G21_phase1_no_hot_start` — T_mean steps 1-10 < 320 K (s107 lesson)
  - `G22_phase2_no_T_drift` — |T_slope| < 5 K/ps (F-045 lesson)
  - `G23_hill_units_explicit` — WW unit specifier present (CP2K Hartree gotcha)
  - `G24_wall_correction_applied` — if wall sampled, F_real - V_wall

---

### D-21 | 2026-05-10 | MDCalculation kind with md_protocol + trajectory_analysis + results_md
- **Decision:** new `kind: MDCalculation` for plain MD (not enhanced sampling). Required sections: `md_protocol` (ensemble + thermostat + timestep + duration), `results` (results_md). Optional `trajectory_analysis` (msd, rdf, vacf, hbond_lifetime, diffusion_coefficient, grotthuss_hops, speciation).
- **Source:** W1 grotthuss CP2K AIMD (s107-s136 RUNNING) — real pilot.
- **Pilot:** `examples/w1_grotthuss_aimd.tm.yaml`.
- **Breaking:** NO.

### D-22 | 2026-05-10 | MLIPBenchmark kind with benchmark_setup + metrics + results_mlip_bench
- **Decision:** new `kind: MLIPBenchmark` for cross-method comparison (not a description of a single run, but a **comparison** across backends ± DFT reference). Required: `benchmark_setup` (reference + test_systems + test_observables), `metrics` (Ea_RMSE, abs_diff_saddle, frac_correct_basin etc.), `results` (results_mlip_bench with per_backend + verdict).
- **Source:** W2 US comparison s136 (MACE vs CHGNet vs DFT WT-MetaD).
- **Pilot:** `examples/w2_mlip_benchmark.tm.yaml`. Distinct from `w2_us_pmf.tm.yaml` (that file describes the run EVENT; this file describes the ANALYSIS comparison).
- **Breaking:** NO.

### D-20 | 2026-05-10 | Q115_NOMAD_BENCHMARKS confirms nspin=1 + U=0 for mack/pent
- **Decision:** our current setup (`nspin=1`, U=0 for mack/pent/pyr) is community mainstream 2014-2026; **no justification is needed** in the paper. Tier 1 AFM+U=2 sensitivity (if included in SI) uses U=2, not U=4 (literature standard: Devey 2009 / Williams 2022 / Safeer cRPA 2026).
- **Source:** `knowledge/Q115_NOMAD_BENCHMARKS.md` — 17 verified DOI/MP-IDs across 5 minerals. Devey 2008-2009 explicitly: "U>0 → unphysical for mackinawite Fe-3d delocalization".
- **Impact on pilots:** mack_vfe_neb pilot rewritten from `state: AFM-G + U=4` to `state: NM + U=0` (correctly reflects the s133 real script).
- **Adjustment for Tier 1 sensitivity (if included in SI):** `starting_magnetization` ±2.5 μB (not ±1.0) — avoids FM collapse.
- **Breaking:** YES for pilots, NO for schema (NM/U=0 already valid). Applied to mack_vfe_neb pilot 2026-05-10.

---

## Open [QUESTION]

### Q-TMSPEC-9 [2026-05-10] — Recipe registry for inverse conversion (Lotsman runtime)

**Concept:** TM-Spec → executable Python script via recipe template engine. Inverse `tm_spec_extract.py`.

**Architecture:**
```yaml
# New block in TM-Spec (optional):
recipe:
  name: canonical_neb_qe_vacancy_hop
  version: 1.0
  runtime: native                       # see Q-TMSPEC-10
  overrides:
    hop_mode: diagonal
    pseudo_dir: /opt/pp/oncv_pbe
```

**Do NOT encode algorithm logic in YAML** (Turing-complete trap). Only pointer + parameters.

**Recipe registry structure:**
```
tools/tm_recipes/
├── canonical_neb_qe_vacancy_hop.py
├── canonical_neb_qe_vfe_proton_pair.py
├── plain_md_cp2k_aimd.py
├── us_pmf_mlip_native.py
├── wt_metad_cp2k.py
└── _builders/                          # shared functions: pick_triple, prewrap, place_h
```

Each recipe is a Python class with `render(doc) → str` (jinja2 or f-strings) → ready-to-exec script source.

**Lotsman workflow** (`lotsman.execute_tm_spec(yaml, instance)`):
1. Validate (our `tm_spec_validator`)
2. Resolve recipe by `name@version`
3. Render → script source + sha256 hash
4. Deploy to instance (Lotsman already supports this)
5. Watch + harvest (Lotsman already supports this)
6. Auto-fill (our `tm_spec_sanity_fill`)
7. Update provenance (host, walltime, cost, hash)
8. Return updated YAML

**Benefits:**
- TM-Spec becomes an **executable** specification (not just docs)
- Round-trip test: extracted YAML + recipe → generated script ≈ original script
- NOMAD-ready: updated YAML → `tm_spec_export_nomad` → ZIP → upload (full pipeline)
- Reproducibility: TM-Spec + recipe@version + script_hash = bit-exact run

**Pitfalls:**
- Recipe versioning compatibility (SemVer + backward-compat layer)
- Custom logic escape hatch (`recipe.overrides.custom_python` — last resort, document in `notes`)
- Recipe dependencies (Python packages, image tags) — declare via `recipe.requirements` or Docker tag

**PoC plan (~3 hr):**
1. Add `recipe` block to schema (optional, 10 min)
2. One recipe `canonical_neb_qe_vacancy_hop` (port `neb_canonical_pyr_96at_qe.py`, 90 min)
3. `tools/tm_spec_to_script.py` generator (30 min)
4. Round-trip test pyr_smoke.tm.yaml + recipe → script vs original (20 min)
5. Lotsman API stub `execute_tm_spec()` (30 min)

**Status:** [DEFERRED] — after paper #1 submission (next week). Recipe registry is a medium-term investment; payoff after 5+ submissions.

---

### Q-TMSPEC-10 [2026-05-10] — Runtime backends (native vs AiiDA vs atomate2)

**Question:** should we reuse AiiDA WorkChains / atomate2 Makers as backends for recipes?

**Reality check (analysis 2026-05-10):**

| Backend | Reusable for | NOT reusable |
|---|---|---|
| **AiiDA** + `aiida-quantumespresso`/`aiida-cp2k` | Standard relax/NEB/MD WorkChains; native provenance graph; `aiida-nomad` upload | ASE issue #1130 fix; custom triple picker (diagonal mode); MLIP US PMF; Vast.ai ephemeral (requires permanent host for daemon + Postgres + RabbitMQ) |
| **atomate2** Makers | Pydantic-typed input sets; emmet TaskDoc compat; Maker pattern as design inspiration | NEB Maker still in development 2026; VASP-biased (~80%); not for CP2K WT-MetaD / MLIP US |

**Decision:** **hybrid runtime** — TM-Spec supports multiple backends via `recipe.runtime`:
- `native` (default) — our registry, ASE scripts. For Vast.ai ephemeral + custom patches + MLIP US (~80% of our cases).
- `aiida` — TM-Spec → AiiDA WorkChain inputs converter. For standard recipes on a permanent host (gomer) when full provenance graph is desired.
- `atomate2` — for future VASP work (currently 0%).

**What is worth adopting (without full reuse):**
1. **Provenance schema:** D-12 cement — use AiiDA `LinkType` enum on export (`INPUT_CALC`, `INPUT_WORK`, `CALL_CALC`, `CALL_WORK`, `CREATE`, `RETURN`).
2. **`aiida-common-workflows`** input conventions — standard keys for cross-code workflows (relax, eos, bands). Use as inspiration for recipe.overrides naming.
3. **`aiida-nomad` upload mapping** — cross-check with our `tm_spec_export_nomad.py`; align mappings (we have it; reuse validation logic).

**Status:** [DEFERRED]. Native backend covers paper #1 submission. AiiDA wrapper — v0.5 if demand arises (e.g., reviewer requests a full AiiDA provenance archive).

---

### Q-TMSPEC-12 [2026-05-10] — Strategic positioning vs AiiDA/atomate2/AiiDAlab

**Question:** are we competing with industry standards (AiiDA) or finding a complementary niche?

**Landscape analysis:** see `LANDSCAPE.md` for a detailed table (10 tools).

**Closest competitor — AiiDAlab QE** (https://github.com/aiidalab/aiidalab-qe). Web app on top of AiiDA for declarative QE input. Addresses the "scientist without Python" use case, but: web app (not git-tracked text), QE-only, AiiDA daemon required.

**Decision:** **complementary positioning**, not head-to-head competition.

**4 niches where TM-Spec can claim a position:**
1. **Paper SI format** — no one provides declarative cross-code SI. **Unique value.**
2. **Ephemeral cloud compute** — AiiDA is not compatible with Vast.ai. Lotsman + TM-Spec = niche.
3. **Domain-specific recipes** — encyclopedia of patches for Fe-S (extensible to oxides/MOFs).
4. **Educational / reproducibility** — bit-exact reproduction via YAML + cloud GPU.

**Strategic recommendations:**
1. Do NOT position as "AiiDA-killer"
2. Paper #1 SI = first publication-grade artefact (test case)
3. After submission, if reviewer feedback is positive — release TM-Spec on GitHub under MIT
4. AiiDA-bridge converter — deferred until community request
5. Long-term: TM-Spec for **paper-grade reproducibility**, AiiDA for **lab-internal provenance**. They coexist.

**Precedents (how small declarative formats became standards):**
- `requirements.txt` (~5 years to standard)
- `Dockerfile` (5 years, conquered industry)
- `schema.org` JSON-LD (via Google adoption)
- `citation.cff` (~3 years, GitHub native support)

All grew from: **simple text + tool ecosystem + early adopters**. TM-Spec already has the first two.

**Main risk:** over-scoping to a scale we cannot sustain (AiiDA-killer → failure; narrow Fe-S DSL → may work).

**Status:** [DECIDED] — complementary positioning. Paper #1 submission = test case for niche validation.

---

### Q-TMSPEC-11 [2026-05-10] — Pydantic recipe inputs (atomate2 reuse?)

**Question:** should we use `atomate2` Pydantic input sets (e.g. `MPRelaxSet`, `NEBSet`) as a type-checked structure for `recipe.overrides`?

**Pros:**
- Type-checking + IDE auto-completion
- Compatibility with emmet TaskDoc Pydantic models (D-04 already aligned)
- No need to write validation by hand

**Cons:**
- atomate2 Sets are VASP-centric (`MPRelaxSet` uses INCAR keys: `ENCUT`, `LDAUU`); for QE pwscf these keys are irrelevant — a `QESet` is needed (not available in atomate2).
- Adds dependency: `pip install atomate2` (heavy: pulls jobflow, pymatgen, custodian).

**Alternative:** a minimal in-house Pydantic layer (`pydantic` is already in our dependencies via FastAPI/etc). Simple dataclass-like models for each recipe.

**Decision (preliminary):** in-house Pydantic layer for recipe.overrides validation, **but adopt naming conventions from atomate2** (e.g., `relax_set.encut_ry`, not `cutoff_wfc`). For cross-code consistency.

**Status:** [DEFERRED] — resolved at PoC implementation stage of Q-TMSPEC-9.

---

- **Q-TMSPEC-2** — MLIP fine-tuning datasets schema (training/val/test split, model checkpoint hash). Trigger: kind `MLIPBenchmark`.
- **Q-TMSPEC-3** — `tm-spec → qcschema` exporter feasibility (no QCSchema NEB analog exists).
- **Q-TMSPEC-4** — NOMAD upload mapping deep dive (manual check of `runschema` plugin field names required).
- **Q-TMSPEC-5** — Markdown SI vs YAML SI convention for paper #1.
- **Q-TMSPEC-6** — Hash strategy (what to hash: script + atoms + level? outputs only?).
- **Q-TMSPEC-7** [NEW] — Trajectory storage: inline (extxyz refs) vs OPTIMADE 1.4 trajectories extension (still draft 2026).
- **Q-TMSPEC-8** [NEW] — Multi-cell support (3×3×1 vs 3×3×2 mack as separate artefacts with the same parent structure) — currently via `supercell: [3,3,1]` field, but cell-specific overrides for defects/magmoms may be needed.
