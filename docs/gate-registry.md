# TM-Spec Sanity Gate Registry

Canonical vocabulary of sanity gate IDs used in the `sanity[]` array (post-hoc, filled
from run artefacts) and the `preflight.gates[]` array (predictive, filled before the run
by a pre-flight engine such as **Prodromos**). One ID means the same check in both places —
the only difference is *when* it is evaluated.

> Status: **draft, introduced in tm-spec/0.3.** IDs match the schema pattern
> `^G\d{2}_[A-Za-z0-9_]+$`. Additive: new gates get the next free number; existing IDs are
> stable. Cost is a rough order-of-magnitude for the *predictive* evaluation.

## Why a registry

`sanity` and `preflight` share one ID space so that a document can be checked *before* a
calculation (prediction) and *after* it (observation) with the same gate, and the two can
be compared. The post-hoc filler is `tm_spec.sanity_fill`; the predictive provider is an
external engine. The `engine` column names the reference predictive implementation; the
gate is engine-agnostic.

## Registry

| ID | Checks | Predictive engine (gate) | Cost (predict) | Notes |
|----|--------|--------------------------|----------------|-------|
| `G01_FeS_bond` | min(Fe–S) above a physical floor | (structural sanity) | $0 | runtime/structural |
| `G02_moment_not_collapsed` | local TM moment collapses vs persists (nspin=1≡2?) | prodromos `spin-collapse` | $0 (1 MLIP/cheap SP) | decides nspin |
| `G03_endpoints_distinct` | endpoints A,B are different basins (not same-basin) | prodromos `symmetry-preflight` (Hungarian L1) | $0 | strongest same-basin predictor |
| `G04_fmax_endpoints` | endpoint forces below target | (runtime) | n/a | post-hoc |
| `G05_scf_converged` | all images SCF converged | (runtime) | n/a | post-hoc |
| `G06_ascii_safe` | no non-ASCII in deploy script | prodromos `lint-dft-script` | $0 | deploy lint |
| `G07_singleton_lock` | launch singleton guard present | (runtime) | n/a | infra |
| `G08_idpp_prewrap` | IDPP prewrap applied to band | (runtime) | n/a | post-hoc |
| `G09_geometry_origin` | endpoint geometry_origin is dft_relaxed, not an MLIP geometry | prodromos `endpoint-provenance` | $0 | energy validity; local bond geometry necessary but not sufficient |
| `G10_global_displacement` | non-H displacement not implausibly global | prodromos `symmetry-preflight` | $0 | flags non-stationary MLIP endpoint |
| `G11_electron_parity` | electron count parity vs nspin choice | prodromos `electron-parity` | $0 | odd+fixed-occ → nspin=2 mandatory |
| `G12_endpoint_single_sheet` | endpoints on one magnetic sheet | prodromos `magnetic-endpoint` | $0 (parse) | GO / NO-GO_SINGLE_SHEET |
| `G13_band_single_sheet` | no spin-sheet crossing inside the band | prodromos `magnetic-band` | $0 (parse) | post-pilot |
| `G14_magnetization_settled` | moment converged, not still drifting | prodromos `magnetic-parser` | $0 (parse) | drift window |
| `G15_provenance_consistent` | compared energies share (U,nspin,functional,ecut,kpts) | prodromos `magnetic-parser` / within-method delta | $0 | refuses cross-method comparison |
| `G16_method_recommendation` | NEB failure signature → method family | prodromos `neb-advisor` | $0 | band / dimer+chemical-RC / string |
| `G17_saddle_on_path` | saddle is the intended transfer, not off-path | prodromos `saddle-proximity` | $0 | DIRECT_TRANSFER_OK |
| `G18_dft_script_lint` | 4 recurring QE/ABACUS deploy bugs | prodromos `lint-dft-script` | $0 | abs pseudo_dir, outdir nesting, clean-read, number_of_wfc>0 |
| `G19_external_reference` | public DFT reference exists (NOMAD/OPTIMADE) | prodromos `external-reference` | $0 (network) | NO_EXTERNAL_REFERENCE raises the bar |
| `G20_h_barrier_paper_grade` | barrier has index-1 H-mode + ΔZPE‡ | prodromos `h-barrier-readiness` | $0 | PAPER_GRADE vs ELECTRONIC_ONLY |

## Relationship to Prodromos backlog IDs

Prodromos tracks its own internal improvement IDs (N-01…N-15). The mapping is recorded in
the Prodromos repository (`ROADMAP.md`); this registry is the **spec-side canonical**
vocabulary and is the source of truth for the `id` field. A predictive engine MUST emit
IDs from this registry (or propose additions via a spec PR).

## Adding a gate

1. Pick the next free `GNN`.
2. Add a row here with the rule and (if applicable) the reference predictive engine.
3. The same ID is then valid in both `sanity[]` and `preflight.gates[]`.
