# TM-Spec ↔ Existing Standards Alignment

> Date: 2026-05-09. Source: web research via WebSearch +
> WebFetch (see **Sources** section at the end). Goal — align field names,
> enum values, and required/optional status of TM-Spec v0.2 with mature
> domain standards (2025-2026) so that downstream NOMAD upload /
> OPTIMADE query / QCSchema interop work without ad-hoc mapping.

Notation:
- `[FACT]` — verified from first-party spec.
- `[CLAIM]` — stated in paper/wiki, not verified in source code.
- `[NOT_VERIFIED]` — WebFetch could not retrieve access; manual check needed later.

---

## 1. NOMAD Metainfo (computational data schema)

- **Spec URL:** https://nomad-lab.eu/prod/v1/docs/explanation/data.html (concept);
  https://nomad-lab.eu/prod/v1/gui/analyze/metainfo/ (interactive browser).
- **Plugin source (canonical schema 2025):**
  https://github.com/nomad-coe/nomad-schema-plugin-run (v1.0.5, 2025-10-30).
- **Wiki (legacy 2017-2020 metainfo):**
  https://gitlab.mpcdf.mpg.de/nomad-lab/nomad-meta-info/-/wikis/metainfo
  — **archived, read-only**. Therefore 2025-canonical = `runschema` plugin.
- **Status:** [CLAIM] Hierarchy `Run → Method → DFT → XCFunctional` confirmed
  via architectural descriptions in FAIRmat tutorial, but exact field names of the plugin
  could not be retrieved from the GitHub UI via WebFetch.

### Imports
- Code-agnostic level-of-theory: a single schema for VASP/QE/CP2K/ABACUS/GPAW, etc.
- Hierarchy: `EntryArchive.section_run.section_method.section_XC_functional`
  (legacy) → `Run.method.dft.xc_functional` (current plugin) [CLAIM].
- LibXC naming convention for XC functionals: `GGA_X_PBE`, `GGA_C_PBE`,
  `HYB_GGA_XC_HSE06`, `MGGA_X_SCAN`. One functional = split into `_X` (exchange)
  + `_C` (correlation) + optional `_XC`.

### Naming (key fields)
- `Run.program.name` — string ("VASP", "QuantumESPRESSO", "CP2K") [CLAIM].
- `Run.program.version` — string ("7.3.1") [CLAIM].
- `Run.method.electronic_structure_method` — enum: `DFT`, `DFT+U`, `G0W0`,
  `MP2`, `CCSD(T)`, `tight_binding`, `MM`, `ML` [CLAIM].
- `Run.method.dft.xc_functional` — list of LibXC IDs.
- `Run.method.basis_set` — enum: `plane_waves`, `gaussians`, `numeric_AOs`,
  `mixed`.
- `Run.method.k_mesh.grid` — `[Nx, Ny, Nz]`.
- `Run.method.k_mesh.offset` — `[fx, fy, fz]`.
- `Run.method.smearing.kind` — enum: `gaussian`, `fermi`, `methfessel-paxton`,
  `marzari-vanderbilt`, `tetrahedra`.
- `Run.method.smearing.width` — float, units **Joule** (NOMAD SI internal).

### Enums
- **XC functional names** (LibXC): `GGA_X_PBE` + `GGA_C_PBE` for PBE,
  `HYB_GGA_XC_HSE06` for HSE06, `MGGA_X_SCAN` + `MGGA_C_SCAN` for SCAN.
- **vdW correction** — separate subsection `Method.vdw_method`: `D2`, `D3`,
  `D3-BJ`, `TS`, `MBD`, `XDM` [CLAIM].
- **DFT+U formulation** — `Dudarev` (single Ueff) or `Liechtenstein` (U+J).

### TM-Spec mismatch
| TM-Spec field | NOMAD recommends | Decision |
|---|---|---|
| `level.xc: PBE+D3(BJ)` | split into: `xc_functional: ["GGA_X_PBE", "GGA_C_PBE"]` + `vdw_method: D3-BJ` | **adopt hybrid:** keep `xc: PBE+D3(BJ)` for human-readable, add `xc_libxc: [GGA_X_PBE, GGA_C_PBE]` + `vdw: D3-BJ` for machine mapping |
| `level.smearing.kind: Marzari-Vanderbilt` | `marzari-vanderbilt` (lowercase, hyphen) | **adopt** lowercase enum |
| `level.smearing.width_Ry` | `width` in Joule | keep eV/Ry for human; add `width_J` when exporting to NOMAD |
| `level.basis.kind: PW` | `plane_waves` | **adopt** `plane_waves` as primary, `PW` as alias |
| `code.name: QuantumESPRESSO` | `Run.program.name` | **adopt** field path, value match |
| `hubbard.Fe-3d.formulation: Dudarev` | `Method.dft.dft_plus_u.formulation: Dudarev` | **adopt** capitalisation (Dudarev/Liechtenstein) |

---

## 2. OPTIMADE (structures endpoint)

- **Spec URL:** https://www.optimade.org/specification/latest/ — **v1.3.0**
  (current), https://schemas.optimade.org/defs/v1.2/ — v1.2 schemas.
- **GitHub:** https://github.com/Materials-Consortia/OPTIMADE
- **Status:** [FACT] for v1.2.0 properties (verified via
  schemas.optimade.org); [CLAIM] for v1.3.0 (latest spec page upgraded
  2025).

### Imports
- Full schema for Structures + Files + References + Calculations entries.
- Property requirement levels: `MUST`, `SHOULD`, `MAY` (via
  `x-optimade-requirements` in JSON).
- Pydantic-compatible JSON Schema.

### Naming (key fields, structures entry)
- `id` — string [MUST].
- `type: "structures"` — string [MUST].
- `elements` — list of element symbols, alphabetical [SHOULD].
- `nelements` — int [SHOULD].
- `elements_ratios` — list of floats, sum=1 [SHOULD].
- `chemical_formula_descriptive` — human-readable string [SHOULD].
- `chemical_formula_reduced` — strict alphabetical reduced [MUST in v1.3].
- `chemical_formula_anonymous` — A1B2 notation [SHOULD].
- `chemical_formula_hill` — C-first then H, then alphabetical [MAY].
- `lattice_vectors` — `[[ax,ay,az],[bx,by,bz],[cx,cy,cz]]` Å [SHOULD,
  REQUIRED if response_fields not specified].
- `cartesian_site_positions` — list `[[x,y,z], ...]` Å [REQUIRED if no fields].
- `nsites` — int [REQUIRED if no fields].
- `species_at_sites` — list of strings (species names) [REQUIRED].
- `species` — list of objects with `name`, `chemical_symbols`, `concentration`,
  optional `mass`, `attached`, `nattached`.
- `dimension_types` — `[0|1, 0|1, 0|1]` [OPTIONAL].
- `nperiodic_dimensions` — int 0..3 [OPTIONAL].
- `last_modified` — ISO timestamp [SHOULD].
- `structure_features` — enum list (see below).

### Enums
- **`structure_features`:** `disorder`, `implicit_atoms`, `site_attachments`,
  `assemblies`. Empty list `[]` means "ordered, fully described".
- **`species.chemical_symbols`** — periodic table symbols + `"X"` (unknown) +
  `"vacancy"`.
- **`dimension_types`** — each of the 3 elements is 0 (non-periodic) or 1 (periodic).

### TM-Spec mismatch
| TM-Spec field | OPTIMADE | Decision |
|---|---|---|
| `structure.formula: Fe16S16` | `chemical_formula_descriptive: "Fe16S16"` + `chemical_formula_reduced: "FeS"` + `chemical_formula_anonymous: "AB"` | **adopt** — add three formula fields on export |
| `structure.cell.a / .c / .gamma` | `lattice_vectors: [[a,0,0],[0,a,0],...]` Cartesian Å | **keep** human-readable a/b/c/α/β/γ; add computed `lattice_vectors` |
| `structure.pbc: [true,true,true]` | `dimension_types: [1,1,1]` + `nperiodic_dimensions: 3` | **adopt** both forms (boolean primary, ints for OPTIMADE export) |
| `structure.wyckoff: {Fe@2a: [0,0,0]}` | `cartesian_site_positions` + `species_at_sites` (no explicit Wyckoff) | **keep** Wyckoff for human; expand into species/positions on export |
| `kind: NEBCalculation` | OPTIMADE has only `structures`/`references`/`files`/`calculations`/`trajectories` (draft) | **note:** TM-Spec NEB is not covered by OPTIMADE 1.3; requires trajectories extension v1.4+ |

---

## 3. QCSchema (MolSSI Quantum Chemistry Schema)

- **Spec URL:** https://github.com/MolSSI/QCSchema (canonical repo);
  https://molssi.github.io/QCElemental/ (Python implementation).
- **Versions:** schema_version=1 (stable), schema_version=2 (development,
  in `qcschema/data/v2/`).
- **Status:** [FACT] for Molecule fields (verified via QCSchema dev/molecule.py).

### Imports
- Standardised JSON for quantum chemistry input/output.
- Drivers (energy/gradient/hessian/properties) — unified interface.
- Pydantic models via `qcelemental`.

### Naming (key fields)
- **Molecule** (`schema_name: qcschema_molecule`):
  - `symbols` — list of element symbols (Title case).
  - `geometry` — flat list `[x1,y1,z1,x2,...]` in **Bohr (a0)** [FACT — units].
  - `atomic_numbers`, `mass_numbers`, `masses`, `atom_labels`.
  - `molecular_charge` (default 0.0), `molecular_multiplicity` (default 1).
  - `connectivity` — list of `[atom_i, atom_j, bond_order]`.
  - `fragments`, `fragment_charges`, `fragment_multiplicities`.
  - `fix_com`, `fix_orientation`, `fix_symmetry`.
  - `provenance` — object (creator, version, routine).
  - `extras` — free-form dict.
- **AtomicInput** (`schema_name: qcschema_input`):
  - `model: { method: "PBE", basis: "def2-svp" }` — XC and basis in one object.
  - `driver` — enum.
  - `keywords` — code-specific dict.
  - `molecule` — Molecule object.
- **AtomicResult** (`schema_name: qcschema_output`):
  - `properties: AtomicResultProperties` (energies, dipole, etc.).
  - `return_result` — driver-dependent (scalar / array / object).
  - `success: bool`, `error: ComputeError | None`.
  - `wavefunction: WavefunctionProperties | None`.
- **OptimizationResult**:
  - `final_molecule` — Molecule.
  - `trajectory` — list of AtomicResult (per step).
  - `energies` — list of floats.

### Enums
- **`driver`:** `energy`, `gradient`, `hessian`, `properties`.
- **`schema_version`:** `1` or `2`.
- **`schema_name`:** `qcschema_molecule`, `qcschema_input`, `qcschema_output`,
  `qcschema_optimization_input`, `qcschema_optimization_output`.

### TM-Spec mismatch
| TM-Spec field | QCSchema | Decision |
|---|---|---|
| `level.xc: PBE+D3(BJ)` | `model.method: "PBE-D3BJ"` (single string) | **note:** QCSchema is not strict about vdW; multiple encodings exist (PBE-D3, PBE+D3BJ). Adopt `model.method` as human string; separate `model.dispersion: D3BJ` in extras |
| `level.basis: { kind: PW, cutoff_Ry: 80 }` | `model.basis: "PW"` (string) — no PW deep specs | **mismatch:** QCSchema is biased toward Gaussian basis sets. Keep TM-Spec rich `basis` block; on export → `model.basis: "PW-80Ry"` string |
| `structure.cell` (Å) | `Molecule.geometry` in **Bohr** | **note:** unit conversion required on export (1 Å = 1.8897 a0) |
| `kind: NEBCalculation` | no equivalent — QCSchema has only OptimizationResult / TorsionDriveResult | **mismatch:** TM-Spec NEB requires a custom QCSchema-like extension |
| `results.Ea_forward_eV` | `properties.return_energy` in **Hartree** | **note:** unit conversion (1 eV = 0.0367 Ha) |

---

## 4. magCIF (IUCr magnetic CIF dictionary)

- **Spec URL:** https://www.iucr.org/resources/cif/dictionaries/browse/cif_mag
  (current version **0.9.8**, approved 2016, refined 2024).
- **PDF:** https://www.iucr.org/__data/iucr/cif/dictionaries/cif_mag_0.9.8.dic.pdf
  (HTTP 403 from WebFetch, but publicly available).
- **Child standard:** MAGNDATA (Bilbao) — 2000+ structures in magCIF format.
- **Status:** [FACT] for main datanames (verified via IUCr index page).

### Imports
- Standardised description of magnetic structure — symmetry group, moments,
  propagation vectors. Compatible with FullProf, JANA2020, ISODISTORT.

### Naming (key fields)
- `_atom_site_moment.label` — string, refers to `_atom_site.label`.
- `_atom_site_moment.crystalaxis_x` / `_y` / `_z` — float, **μ_B** units,
  components along unit cell axes.
- `_atom_site_moment.Cartn` — moment in orthogonal Cartesian (x‖a, z‖c*).
- `_atom_site_moment.magnitude` — |m| in μ_B.
- `_atom_site_moment.symmform` — symmetry constraint form.
- `_space_group_magn.name_BNS` / `_OG` — Belov-Neronova-Smirnova (BNS) or
  Opechowski-Guccione (OG) magnetic space group notation.
- `_space_group_magn.number_BNS` — int (e.g., 62.448).
- `_parent_space_group.name_H-M_alt` — parent crystallographic SG.
- `_parent_space_group.transform_Pp_abc` — parent → magnetic transformation.
- `_parent_propagation_vector.kxkykz` — `[1/2, 1/2, 0]` or string format.
- `_atom_site_moment_modulation.*` — for incommensurate modulated structures.

### Enums
- **Magnetic space group convention:** `BNS` (recommended) or `OG`.
- **Propagation vector type:** `commensurate` or `incommensurate`.
- Example string `_space_group_magn.name_BNS: "P_b 4'/n m m'"` (mackinawite-like).

### TM-Spec mismatch
| TM-Spec field | magCIF | Decision |
|---|---|---|
| `magnetic.state: AFM-G` | no such enum. Described via BNS group + magmoms | **keep** TM-Spec abbreviation (AFM-G/A/C, FM, ferri, NM) — convenient shortcut. ADD optional `magnetic.bns_group: "..."` for magCIF export |
| `magnetic.collinear: true` | implicit — moment vectors have only 1 non-zero component | **keep** boolean; verify collinearity on export |
| `magnetic.propagation_vector: [0,0,0]` | `_parent_propagation_vector.kxkykz: "0 0 0"` | **adopt** — our format is already close |
| `magnetic.magmoms_uB.Fe[top]: +3.5` | `_atom_site_moment.crystalaxis_z: 3.5` (per-atom) | **expand** on export: one moment entry per Fe in the asymmetric unit, with label |
| `magnetic.surrogate_warning` | no equivalent in magCIF | **keep** — this is our original semantics for the PBE PM/itinerant proxy |

---

## 5. AFLOW Prototype Encyclopedia

- **Spec URL:** https://aflowlib.org/p/Tutorials/AFLOW_Prototype_Label/
- **Library Part 4 (2024 update):**
  ScienceDirect S092702562400209X — `+683 prototypes → 1783 total`,
  standardized label protocol.
- **Status:** [FACT] for label format.

### Imports
- Compact text label that fully identifies a prototype: stoichiometry +
  Pearson + space group + Wyckoff letters per element.

### Naming (label format)
Format: `<stoichiometry>_<Pearson>_<SGnum>_<Wyckoff_per_element>[-<index>]`

Components:
1. **Stoichiometry** — A, AB, AB2, A2B3, ABC2... (alphabetical, subscripts inline).
2. **Pearson symbol** — letter (a/m/o/t/h/c) + (P/I/F/R/A/B/C centering) + atom count.
3. **Space group number** — IT 1-230.
4. **Wyckoff letters per element** — alphabetical, separated by `_`.
5. **`-NNN` suffix** — index if multiple structures share the same label.

Examples decoded (verified):
- `A_cF4_225_a-001` = Cu (FCC, SG 225 Fm-3m, single Wyckoff 4a).
- `AB_cF8_225_a_b-001` = NaCl.
- `AB_tP4_129_a_c` = mackinawite-like (tetragonal P4/nmm).
- `AB2C4D_oP32_34_ab_abc_4c_c-001` = K2AgSbS4.

### Enums
- **Pearson lattice letters:** `a` (triclinic), `m` (monoclinic), `o` (orthorhombic),
  `t` (tetragonal), `h` (hexagonal/trigonal/rhombohedral), `c` (cubic).
- **Pearson centering:** `P` (primitive), `I` (body-centered), `F` (face-centered),
  `R` (rhombohedral), `A`/`B`/`C` (single-face-centered).

### TM-Spec mismatch
| TM-Spec field | AFLOW | Decision |
|---|---|---|
| `structure.prototype: AB_tP4_129_a_c` | format match | **adopt fully** — our draft is already correct |
| `structure.space_group: { number: 129, symbol: P4/nmm }` | redundant with prototype | **keep** SG for human readability, prototype for machine matching |
| Wyckoff `Fe@2a: [0,0,0]` | AFLOW does not include coordinates in the label, only letters | **keep** our expanded Wyckoff format (coordinates + letter) |

---

## 6. AiiDA provenance graph schema

- **Spec URL:** https://aiida.readthedocs.io/projects/aiida-core/en/stable/
  (current 2.7.3, 2025).
- **News:** https://www.aiida.net/news/posts/2025-09-05-orm.html — pydantic
  models for all ORM Entity types (2025-09).
- **Status:** [FACT] for link types (verified via provenance/concepts page);
  [CLAIM] for pydantic field names (new API 2.7).

### Imports
- DAG with two node kinds: **ProcessNode** (calc/workflow execution) and
  **Data** (StructureData, Dict, ArrayData, ...).
- Directed links with types separating **data provenance** (what created what)
  and **logical provenance** (workflow called processes).
- Pydantic 2.7+ models with automatic JSON serialization.

### Naming (Node fields)
- Generic `Node`:
  - `uuid` — UUID4 string.
  - `pk` — int (primary key in local DB).
  - `node_type` — string class path.
  - `process_type` — string (for ProcessNodes).
  - `label` — short human label.
  - `description` — long description.
  - `ctime` / `mtime` — created/modified timestamps.
  - `attributes` — dict[str, Any] (typed attributes).
  - `extras` — dict (mutable user metadata).
  - `repository_metadata` / `repository_content` — file repository (base64).
- `ProcessNode` adds:
  - `process_state` — enum: `created`, `running`, `waiting`, `finished`, `excepted`, `killed`.
  - `exit_status` — int | None.
  - `exit_message` — string | None.
- `CalcJobNode` adds:
  - `state` (CALC_JOB_STATE_KEY).
  - `remote_workdir`.
  - `retrieve_list`.
  - scheduler-related keys.
- `StructureData` (Data subclass):
  - `cell` — 3×3 list.
  - `pbc` — `[bool, bool, bool]`.
  - `kinds` — list of `Kind` (name, symbols, weights, mass).
  - `sites` — list of `Site` (kind_name, position).

### Enums (LinkType)
[FACT] AiiDA `aiida.common.links.LinkType`:
- `INPUT_CALC` — Data → CalculationNode.
- `INPUT_WORK` — Data → WorkflowNode.
- `CREATE` — CalculationNode → Data (output of a calc).
- `RETURN` — WorkflowNode → Data (output of a workflow).
- `CALL_CALC` — WorkflowNode → CalculationNode (workflow called calc).
- `CALL_WORK` — WorkflowNode → WorkflowNode (sub-workflow).

### TM-Spec mismatch
| TM-Spec field | AiiDA | Decision |
|---|---|---|
| `provenance.parents: [tm.mack.vfe.hint.smoke@2026-05-03, Q-115@...]` | edges via INPUT_CALC/INPUT_WORK + uuid links | **keep** human-readable parent IDs (our deliberate design choice); export mapping `parent_id → uuid` via aiida lookup |
| `provenance.author: igor@exopoiesis.space` | `Node.user.email` | **adopt** field path |
| `provenance.compute.cost_usd / walltime_h` | no native fields — stored in `attributes` or `extras` | **keep** our fields; export → `extras.tm_compute` |
| `provenance.hash.inputs/outputs sha256` | AiiDA hashes inputs automatically in `attributes._aiida_hash` | **additionally adopt** on export |
| `id: tm.<system>.<setup>.<method>.<date>` | `Node.label` (string) + UUID | **keep** — `id` → `label`, UUID generated on export |
| TM-Spec links by human-readable parent IDs | LinkType enum | **adopt enum** on serialization: `kind: NEBCalculation` parent type → `INPUT_WORK` or `CALL_CALC` |

---

## 7. Antimony 3 (textual SBML for reactions)

- **Spec URL:** https://tellurium.readthedocs.io/en/latest/antimony.html
- **arXiv:** 2405.15109 (Smith et al., 2024 "An Update to the SBML
  Human-Readable Antimony Language").
- **Versions:** 3.0.0 (June 2025), 3.1.0 (Oct 2025), 3.1.3 (April 2026).
- **Status:** [FACT] for basic syntax.

### Imports
- Minimally punctuated text that compiles to SBML.
- Supports reactions, kinetic laws, compartments, events, modules, FBC.

### Naming (syntax)
- **Reaction:** `[name]: reactants -> products; rate_law`.
- **Reversible:** `J0: A -> B; k1*A - k2*B` or `J0: A <-> B; ...`.
- **Stoichiometry:** `J: 2A + B -> C; k*A^2*B`.
- **Parameter declaration:** `k1 = 0.1;` (after reactions).
- **Species init:** `A = 1.0;`.
- **Compartment:** `compartment cell = 1.0;`.
- **Module:** `model name() ... end`.
- **Rules** (assignment): `:= expr`; **rate rules**: `'`.

### Enums
- **Rate law forms** — free SBML MathML expression, no enum.
  Typical: `k*A` (mass action), `Vm*S/(Km+S)` (MM), `Vmax*S^n/(Km^n + S^n)` (Hill).
- **FBC version 3** (with Antimony 3.1) — gene products, charges, formulas.

### TM-Spec mismatch
| TM-Spec field | Antimony | Decision |
|---|---|---|
| `reactions[].rule: "H_aq^+ + Fe_Fe^× → (H–Fe)_Fe^×"` | `R1: H_aq + Fe_Fe -> H_Fe; k1*H_aq*Fe_free` (no Unicode arrows, no Kröger-Vink superscripts) | **mismatch:** Antimony — ASCII identifiers only. **Hybrid:** keep human-readable Unicode + Kröger-Vink in TM-Spec; on export → ASCII aliases (e.g. `H_aq → H_aq`, `(H-Fe)_Fe^× → H_Fe_x`) |
| `reactions[].rate: "k1 * [H+] * θ_Fe_free"` | `k1*H_aq*theta_Fe_free` | **adopt** rate-law string; mapping `[X] → X`, `θ → theta_` |
| `reactions[].params.k1: { value: 1e-4, units: M^-1·s^-1 }` | `k1 = 1e-4;` (units in comment) | **keep** our rich format; on export → comment `// units: M^-1 s^-1` |
| `reactions[].id: R1` | `R1:` reaction label | **adopt** |
| `reactions[].Ea_eV: 0.043` | absent — Antimony rate-law does not expect activation energy | **keep** for scientific value; derive k via Arrhenius on compilation |

---

## 8. PHREEQC v3 (aqueous geochemistry)

- **Spec URL:** https://water.usgs.gov/water-resources/software/PHREEQC/
  documentation/phreeqc3-html/phreeqc3-48.htm (SOLUTION),
  /phreeqc3-24.htm (KINETICS).
- **Release notes:** https://hydrochemistry.eu/ph3/release.html.
- **Status:** [FACT] for unit/keyword syntax (verified via WebFetch).

### Imports
- Standardised keyword blocks: SOLUTION, EQUILIBRIUM_PHASES, KINETICS,
  RATES, SURFACE, EXCHANGE, SOLUTION_SPECIES, SOLUTION_MASTER_SPECIES.
- Database files: phreeqc.dat, llnl.dat, minteq.dat, sit.dat, pitzer.dat.

### Naming (SOLUTION block identifiers)
- `temp` (or `temperature`, `-t`) — °C.
- `pressure` (or `press`, `-pr`) — atm.
- `pH` — float, optionally `charge` (charge balance flag).
- `pe` — float (negative log of activity of e-).
- `redox` — couple, e.g. `O(-2)/O(0)` or `S(6)/S(-2)`.
- `units` — concentration unit (see enums).
- `density` (or `dens`, `-d`) — kg/L, may be `calculate`.
- `-isotope` — isotope ratios.
- `-water` — kg of water.
- Per-species: `<element> [valence] <conc> [units] [as formula | gfw value] [redox_couple] [charge|phase_name]`.

### Enums
- **`units`** allowed values:
  - Per liter: `mol/L`, `mmol/L`, `umol/L`, `g/L`, `mg/L`, `ug/L`.
  - Per kg solution: `mol/kgs`, `mmol/kgs`, `ppm`, `ppb`, `ppt`, `g/kgs`, `mg/kgs`.
  - Per kg water: `mol/kgw`, `mmol/kgw` (**default**), `umol/kgw`, `g/kgw`, `mg/kgw`.
- **`charge`** flag — applied to one ion for charge balance.
- **`phase_name`** — for saturation-driven concentration (e.g. `Calcite SI 0.0`).

### TM-Spec mismatch
| TM-Spec field | PHREEQC | Decision |
|---|---|---|
| `environment.composition_molal: { Fe(2): 1e-3, S(-2): 5e-4 }` | `Fe(2) 1.0e-3 mol/kgw` | **adopt** PHREEQC element(valence) notation **verbatim** — our format is already close |
| `environment.T: 363.15 K` | `temp 90` (°C) | **mismatch:** PHREEQC uses °C. **Decision:** keep K as primary, add computed `temp_C` on export |
| `environment.pH: 6.0` | match | **adopt** |
| `environment.redox.Eh: -0.40 V_SHE` | `pe` (dimensionless) — no direct Eh | **note:** convert Eh→pe = Eh/(0.05916·T_factor). Keep Eh; auto-derive pe. |
| `environment.database: phreeqc/llnl.dat` | `DATABASE phreeqc.dat` keyword | **adopt** path → DATABASE keyword |
| `environment.saturation_targets: {mackinawite: equilibrium}` | `EQUILIBRIUM_PHASES` block | **keep** our short dict; expand into EQUILIBRIUM_PHASES on export |

---

## 9. Materials Project — emmet-core (TaskDoc / MaterialsDoc)

- **Spec URL:** https://materialsproject.github.io/atomate2/user/docs_schemas_emmet.html
- **GitHub:** https://github.com/materialsproject/emmet (active 2025-2026).
- **Status:** [FACT] for top-level TaskDoc fields (verified via WebFetch atomate2 docs).

### Imports
- Pydantic v2 models with automatic JSON Schema (TaskDoc available for VASP results).
- StructureMetadata mixin adds nsites/elements/composition/symmetry/etc.
- Supports run_type / task_type / calc_type for classification.

### Naming (TaskDoc top-level fields)
- `builder_meta` — software versions (emmet-core, pymatgen).
- `nsites`, `elements`, `nelements`, `composition`, `composition_reduced`,
  `formula_pretty`, `formula_anonymous`, `chemsys`, `volume`, `density`,
  `density_atomic` (StructureMetadata mixin).
- `symmetry` — SymmetryDoc (crystal_system, symbol, number, point_group, ...).
- `tags` — list of strings.
- `dir_name` — calculation directory.
- `state` — completion status.
- `calcs_reversed` — list of CalculationDoc (per step).
- `structure` — final pymatgen Structure (serialized).
- `task_type` — string ("Structure Optimization", "NEB", "Static").
- `task_id`, `task_label`.
- `run_type` — XC functional category (`PBE`, `PBESol`, `SCAN`, `R2SCAN`, `HSE06`).
- `calc_type` — combined `f"{run_type} {task_type}"`.
- `orig_inputs` — original user inputs.
- `input` — InputDoc: structure, parameters (INCAR), pseudo_potentials,
  potcar_spec, xc_override, is_lasph, is_hubbard, magnetic_moments.
- `output` — OutputDoc: structure, energy, energy_per_atom, forces, stress,
  bandgap, density.
- `custodian` — corrections applied.
- `run_stats` — runtime/memory.

### Enums
- **`run_type`:** PBE, PBESol, SCAN, R2SCAN, HSE06, PBE+U, PBESol+U, ...
  (VASP-biased — mostly via pseudopotential + INCAR introspection).
- **`task_type`:** "Structure Optimization", "Static", "NEB", "Phonon", "GW",
  "Frequency Dependent Dielectric", ...
- **`state`:** "successful", "unsuccessful", "error".

### TM-Spec mismatch
| TM-Spec field | emmet-core | Decision |
|---|---|---|
| `results.Ea_forward_eV: { value: 0.043, ci95: [...] }` | no native CI — `output.energy` is a plain float | **keep** our rich format; on export → `output.energy: 0.043` + `extras.ci95: [...]` |
| `results.status: PASS / PRELIMINARY / FAIL / RETRACTED` | `state: successful/unsuccessful/error` | **partial mapping:** PASS→successful, FAIL→unsuccessful, RETRACTED→error, PRELIMINARY→no equivalent. Keep our enum. |
| `results.paper_quotable: bool` | no equivalent | **keep — our original semantics** |
| `results.validated_by: [chemist@opus, physicist@opus]` | no equivalent | **keep — our original semantics** (optionally → `extras.validators`) |
| `calculation.code.name: QuantumESPRESSO` | `builder_meta.pymatgen_version` + parser-implicit | **mismatch:** emmet/atomate2 is VASP-only. Note: TM-Spec extension to non-VASP codes adds `code.*` on top of the emmet schema. |
| `task_type: NEB` | match for NEB | **adopt** when mapping `kind: NEBCalculation → task_type: NEB` |

---

## 10. pymatgen-analysis-defects + doped (defect schemas)

- **pymatgen-analysis-defects:** https://github.com/materialsproject/pymatgen-analysis-defects
  (v2026.3.20 latest).
- **doped:** https://doped.readthedocs.io/ (v3.1.0+, 2025-2026).
- **arXiv:** 2403.08012 (doped paper).
- **Status:** [FACT] (verified via WebFetch on doped.core).

### Imports
- Defect (base): `structure`, `site`, `multiplicity`, `oxi_state`,
  `equivalent_sites`, `symprec`, `angle_tolerance`, `user_charges`.
- Subclasses: Vacancy, Substitution, Interstitial, Polaron (NOT @dataclass —
  regular classes with MSONable).
- doped.DefectEntry: extends pymatgen DefectEntry with metadata
  (degeneracy_factors, conventional_structure, wyckoff, calculation_metadata).

### Naming (key fields)
- `defect.structure` — host pymatgen Structure.
- `defect.site` — PeriodicSite (fractional coords).
- `defect.multiplicity` — site multiplicity.
- `defect.oxi_state` — float | str | None.
- `defect.user_charges` — list of int (for charge state generation).
- `defect.name` — string (auto-generated: `"v_Na"`, `"Al_Si"`, `"Li_i"`).
- `DefectEntry.charge_state` — int.
- `DefectEntry.sc_entry` — pymatgen ComputedStructureEntry (defect supercell).
- `DefectEntry.bulk_entry` — bulk reference.
- `DefectEntry.corrections` — dict of energy corrections.
- `DefectEntry.sc_defect_frac_coords` — tuple (3 floats).
- doped extras: `degeneracy_factors`, `conventional_structure`,
  `conv_cell_frac_coords`, `wyckoff` (label string), `defect_supercell`,
  `bulk_supercell`.

### Enums
- **Defect naming convention** (auto):
  - Vacancy: `v_<element>` (e.g. `v_Fe`).
  - Substitution: `<sub>_<host>` (e.g. `Cu_Zn`).
  - Interstitial: `<element>_i` (e.g. `H_i`).
  - Antisite: `<host_a>_<host_b>` (same as substitution).

### TM-Spec mismatch
| TM-Spec field | pymatgen/doped | Decision |
|---|---|---|
| `defects.reactions[]: "Fe_Fe^× → V_Fe'' + Fe(removed)"` | Kröger-Vink not native. Defect represented as `Vacancy(structure=..., site=...)` object | **keep** Kröger-Vink (more scientific) + add parsed `defects.objects[].name: "v_Fe"` for machine handling |
| `defects.population.V_Fe: { count: 1, conc: 1/144 }` | Defect has no concentration field — that lives in DefectEntry context | **keep**; export → DefectEntry list per supercell |
| `H_i^•` notation (charged interstitial) | doped: `H_i` + separate `charge_state: +1` | **adopt:** separate notation into `name: H_i` + `charge: +1` on export |
| `defects.population.H_int.site: tetrahedral_cavity` | doped: `wyckoff` label or `conv_cell_frac_coords` | **keep** human description; add `wyckoff` label on export |

---

## 11. CHGNet and MACE foundation MLIP (config schema)

- **CHGNet:** https://github.com/CederGroupHub/chgnet (v0.3.0 latest 2025).
- **MACE:** https://mace-docs.readthedocs.io/ (v0.3.13 latest 2025-2026).
- **Status:** [FACT] for variant names (verified via WebSearch).

### MACE-MP-0 variants
- **`small`**, **`medium`**, **`large`** — original 2024 variants.
- **`medium-mpa-0`** (default since v0.3.10) — re-trained on Materials Project A dataset.
- **`large-mpa-0`** — extended.
- API: `mace_mp(model="medium", device="cuda")`.

### CHGNet variants
- **`v0.3.0`** — current default pretrained checkpoint.
- **`v0.2.0`** — legacy.
- API: `CHGNet.load()` (default v0.3.0) or `CHGNet.from_file(...)`.

### TM-Spec recommendation
TM-Spec extension for `kind: MLIPBenchmark` (v0.2):

```yaml
calculation:
  method: MLIP
  level:
    backend: MACE                       # MACE | CHGNet | M3GNet | NequIP | ...
    model: mace-mp-0
    variant: medium-mpa-0               # see foundation_models.py
    version: 0.3.13                     # mace package version
    device: cuda
    fine_tuned: false
    fine_tune_dataset: null             # if fine_tuned=true: ref to dataset
```

---

## Summary of recommendations

| TM-Spec field | Current draft | Standard recommends | Source | Decision |
|---|---|---|---|---|
| `calculation.level.xc` | `PBE+D3(BJ)` | `xc_libxc: [GGA_X_PBE, GGA_C_PBE]` + `vdw: D3-BJ` | NOMAD/LibXC | **hybrid:** keep human + add LibXC alias |
| `calculation.level.smearing.kind` | `Marzari-Vanderbilt` | `marzari-vanderbilt` lowercase | NOMAD | **adopt** lowercase enum |
| `calculation.level.basis.kind` | `PW` | `plane_waves` | NOMAD | **adopt** primary `plane_waves`, alias `PW` |
| `calculation.code.name` | `QuantumESPRESSO` | match (NOMAD `Run.program.name`) | NOMAD | **adopt** field path, no value change |
| `calculation.hubbard.formulation` | `Dudarev` | `Dudarev` capitalised | NOMAD | **adopt** as-is |
| `structure.formula` | `Fe16S16` | `chemical_formula_descriptive` + `_reduced` + `_anonymous` | OPTIMADE | **adopt:** add three formula fields on export |
| `structure.cell.{a,c,gamma}` | human a/b/c/α/β/γ | `lattice_vectors: [[ax,ay,az],...]` Å | OPTIMADE | **keep** human, add computed `lattice_vectors` |
| `structure.pbc` | `[true,true,true]` | `dimension_types: [1,1,1]` | OPTIMADE | **keep** boolean primary, add ints for export |
| `structure.prototype` | `AB_tP4_129_a_c` | match | AFLOW | **adopt** verbatim |
| `defects.reactions[]` | Kröger-Vink string | `Vacancy(name="v_Fe")` + `charge_state: -2` | pymatgen-defects + doped | **keep** Kröger-Vink + add machine `defects.objects[]` |
| `defects.population[].site` | `tetrahedral_cavity` | `wyckoff` label | doped | **adopt** — add `wyckoff` |
| `magnetic.state` | `AFM-G` shortcut | BNS magnetic space group symbol | magCIF | **keep** shortcut + add opt `bns_group` |
| `magnetic.magmoms_uB` | `Fe[top]: +3.5` | `_atom_site_moment.crystalaxis_z: 3.5` per atom | magCIF | **keep** dict; expand on export |
| `environment.composition_molal` | `Fe(2): 1.0e-3` | match (PHREEQC element-valence + mol/kgw default) | PHREEQC | **adopt verbatim** — our format is already correct |
| `environment.T` | `363.15 K` | `temp 90` °C | PHREEQC | **keep K**, computed `temp_C` on export |
| `environment.redox.Eh` | `-0.40 V_SHE` | `pe` dimensionless | PHREEQC | **keep Eh**, auto-derive pe |
| `reactions[].rule` | Unicode arrows + Kröger-Vink | ASCII identifiers `H_Fe + ...` | Antimony | **keep** Unicode primary + add ASCII alias on export |
| `reactions[].rate` | `k1 * [H+] * θ_Fe_free` | `k1*H_aq*theta_Fe_free` | Antimony | **adopt** ASCII on export, `[X]→X`, `θ→theta_` |
| `workflow.kind: NEB` | match | `task_type: NEB` | atomate2/emmet | **adopt** mapping to task_type on export |
| `workflow.endpoints` | `{A,B}` extxyz refs | atomate2 NEB Maker — `images` list | atomate2 | **keep** {A,B,images}; map on export |
| `results.status` | `PASS/PRELIMINARY/FAIL/RETRACTED` | `successful/unsuccessful/error` | emmet | **keep** our richer enum, partial mapping on export |
| `results.paper_quotable` | bool | no equivalent | — | **keep — original TM-Spec semantics** |
| `provenance.parents[]` | human IDs | UUIDs + LinkType edges | AiiDA | **keep** human IDs, lookup map on export |
| `provenance.compute.cost_usd` | float | `extras.tm_compute` | AiiDA | **keep** primary, AiiDA extras on export |

---

## Actions for TM-Spec v0.2

1. **Aliases for NOMAD interop** — add optional fields `xc_libxc[]`, `vdw`,
   `temp_C`, `pe_derived`, `lattice_vectors_A`. Primary fields remain human-readable.
2. **`magnetic.bns_group`** — optional field for magCIF export.
3. **Lowercase smearing enum** — rename `Marzari-Vanderbilt` →
   `marzari-vanderbilt` in draft (breaking change, before schema publication).
4. **`basis.kind`** — `plane_waves` primary, `PW` alias.
5. **Defect machine layer** — add `defects.objects[].name` (auto-generated:
   `v_Fe`, `H_i`) + `charge_state` separate from `^•`/`''` notation.
6. **Antimony export tooling** — `tm-spec → antimony` function in
   `tools/tm_spec_export.py` with auto-aliasing Unicode → ASCII identifiers.
7. **`task_type` mapping table** — `NEBCalculation → "NEB"`,
   `USCalculation → "Umbrella Sampling"` (TM-Spec extension to emmet enum).
8. **MLIP backend schema** (v0.2 kind `MLIPBenchmark`) — `backend`, `model`,
   `variant`, `version`, `fine_tuned`. Use MACE/CHGNet variant names.

---

## Sources

### NOMAD Metainfo
- [NOMAD Repository docs (data schema explanation)](https://nomad-lab.eu/prod/v1/docs/explanation/data.html)
- [NOMAD metainfo legacy wiki — XC functional](https://gitlab.mpcdf.mpg.de/nomad-lab/nomad-meta-info/-/wikis/metainfo/XC-functional) (archived 2024)
- [NOMAD metainfo legacy wiki — electronic structure method](https://gitlab.mpcdf.mpg.de/nomad-lab/nomad-meta-info/-/wikis/metainfo/electronic-structure-method)
- [nomad-coe/nomad-schema-plugin-run (canonical 2025 plugin, v1.0.5)](https://github.com/nomad-coe/nomad-schema-plugin-run)
- [FAIRmat tutorial 14 — custom workflows](https://fairmat-nfdi.github.io/fairmat-tutorial-14-computational-plugins/custom_workflows/)

### OPTIMADE
- [OPTIMADE specification latest (v1.3.0)](https://www.optimade.org/specification/latest/)
- [OPTIMADE 1.2 schemas — lattice_vectors](https://schemas.optimade.org/releases/v1.2.0/v1.2/properties/optimade/structures/lattice_vectors)
- [OPTIMADE 1.2 schemas — chemical_formula_descriptive](https://schemas.optimade.org/defs/v1.2/properties/optimade/structures/chemical_formula_descriptive)
- [OPTIMADE 1.2 standards (full)](https://schemas.optimade.org/defs/v1.2/standards/optimade.html)
- [OPTIMADE GitHub repo](https://github.com/Materials-Consortia/OPTIMADE)
- [OPTIMADE Nature Sci. Data paper (Andersen et al., 2021)](https://www.nature.com/articles/s41597-021-00974-z)
- [OPTIMADE Digital Discovery 2024 update](https://pubs.rsc.org/en/content/articlehtml/2024/dd/d4dd00039k)

### QCSchema (MolSSI)
- [MolSSI QCSchema GitHub](https://github.com/MolSSI/QCSchema)
- [QCSchema dev/molecule.py source](https://github.com/MolSSI/QCSchema/blob/master/qcschema/dev/molecule.py)
- [QCElemental docs (Pydantic implementation)](https://molssi.github.io/QCElemental/)
- [QCSchema overview at MolSSI](https://molssi.org/software/qcschema-2/)
- [QCElemental procedures (OptimizationResult)](http://docs.qcarchive.molssi.org/projects/QCElemental/en/latest/_modules/qcelemental/models/procedures.html)

### magCIF
- [IUCr magnetic CIF dictionary browse (v0.9.8)](https://www.iucr.org/resources/cif/dictionaries/browse/cif_mag)
- [magCIF dictionary PDF (v0.9.8)](https://www.iucr.org/__data/iucr/cif/dictionaries/cif_mag_0.9.8.dic.pdf)
- [magCIF v0.9.8 HTML definitions index](https://www.iucr.org/__data/iucr/cifdic_html/3_orig/MAGNETIC_CIF/index.html)
- [Guidelines for communicating commensurate magnetic structures (IUCr 2024)](https://journals.iucr.org/b/issues/2024/04/00/me6275/index.html)
- [MAGNDATA database (Bilbao)](https://www.cryst.ehu.es/magndata/)
- [MAGNDATA paper (Perez-Mato et al., 2016)](https://onlinelibrary.wiley.com/doi/abs/10.1107/S1600576716012863)

### AFLOW Prototype Encyclopedia
- [AFLOW Prototype Label tutorial](https://aflowlib.org/p/Tutorials/AFLOW_Prototype_Label/)
- [Encyclopedia of Crystallographic Prototypes index](https://aflowlib.org/prototype-encyclopedia/)
- [AFLOW prototype tutorials](https://aflow.org/prototype-encyclopedia/tutorials.html)
- [AFLOW Library of Prototypes Part 4 (2024 update)](https://www.sciencedirect.com/science/article/abs/pii/S092702562400209X)
- [AFLOW-XtalFinder paper (npj Comp Mat 2021)](https://www.nature.com/articles/s41524-020-00483-4)

### AiiDA
- [AiiDA core docs (v2.7.3)](https://aiida.readthedocs.io/projects/aiida-core/en/stable/)
- [AiiDA provenance concepts](https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/processes/concepts.html)
- [AiiDA provenance implementation](https://aiida.readthedocs.io/projects/aiida-core/en/latest/topics/provenance/implementation.html)
- [AiiDA 2.7 ORM pydantic models (2025-09)](https://www.aiida.net/news/posts/2025-09-05-orm.html)
- [AiiDA 1.0 Sci Data paper (Huber et al., 2020)](https://www.nature.com/articles/s41597-020-00638-4)

### Antimony 3 / Tellurium
- [Antimony Reference (Tellurium docs)](https://tellurium.readthedocs.io/en/latest/antimony.html)
- [Antimony arXiv 2024 update](https://arxiv.org/html/2405.15109v1)
- [libAntimony homepage](https://antimony.sourceforge.net/)
- [Antimony PyPI](https://pypi.org/project/antimony/)

### PHREEQC v3
- [PHREEQC v3 SOLUTION keyword](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-48.htm)
- [PHREEQC v3 KINETICS keyword](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-24.htm)
- [PHREEQC release notes](https://hydrochemistry.eu/ph3/release.html)

### Materials Project / emmet / atomate2 / pymatgen-defects / doped
- [emmet docs](https://materialsproject.github.io/emmet/core/)
- [atomate2 task documents and emmet schemas](https://materialsproject.github.io/atomate2/user/docs_schemas_emmet.html)
- [atomate2 GitHub](https://github.com/materialsproject/atomate2)
- [Atomate2 paper (Digital Discovery 2025)](https://pubs.rsc.org/en/content/articlehtml/2025/dd/d5dd00019j)
- [pymatgen-analysis-defects docs](https://materialsproject.github.io/pymatgen-analysis-defects/intro.html)
- [pymatgen-analysis-defects GitHub](https://github.com/materialsproject/pymatgen-analysis-defects)
- [doped docs (v3.1.0)](https://doped.readthedocs.io/en/3.1.0/_modules/doped/core.html)
- [doped paper arXiv 2403.08012](https://arxiv.org/abs/2403.08012)

### MACE and CHGNet
- [MACE foundation models docs](https://mace-docs.readthedocs.io/en/latest/guide/foundation_models.html)
- [MACE foundation_models.py source](https://github.com/ACEsuit/mace/blob/main/mace/calculators/foundations_models.py)
- [CHGNet GitHub](https://github.com/CederGroupHub/chgnet)
- [CHGNet model.py source](https://github.com/CederGroupHub/chgnet/blob/main/chgnet/model/model.py)
- [MatGL paper (npj Comp Mat 2025)](https://www.nature.com/articles/s41524-025-01742-y)
