# Lit-Review: Metalanguages for Scientific Data Description

> Date: 2026-05-09. Audience: self-study prior to extending TM-Spec.
> Goal: understand what is already standardised, to avoid reinventing the wheel
> and instead borrow best practices layer by layer.

---

## TL;DR

**There is no universal "physics/chemistry language."** What exists is a stack of
established domain languages, organised by layer. The most "code-like" ones in our zone:

| Domain | Best language | Why |
|---|---|---|
| Reaction dynamics (CRN/kinetics) | **Antimony 3** | Text like `J0: A->B; k1*A`, converts to SBML, reads like code |
| Atomistics (DFT/MD inputs) | **ASE Python** | Python as de facto DSL over QE/VASP/GPAW/CP2K |
| Defect chemistry | **Kröger-Vink** | Defect equations with charges and sites |
| Hydrothermal environment | **PHREEQC input** | KEYWORD-blocks + balanced equations, all in one file |
| Phase thermodynamics | **CALPHAD TDB** | A real DSL for Compound Energy Formalism |
| Crystal structure | **AFLOW prototype** + CIF | `AB_tP4_129_a_c` — compact signature |
| Cross-DFT interoperability | **NOMAD Metainfo** | Parsers for ~40 codes |
| Materials database queries | **OPTIMADE** | Unified filter language |
| Reproducibility | **AiiDA** | Workflow + provenance graph |

---

# Part 1. Generic / Organic Languages

## 1.1. Structure (static)

- **SMILES / SMARTS / SMIRKS** — linear string for molecules and reactions
  (`CC(=O)O` = acetic acid). De facto standard in organic chemistry.
- **InChI / InChIKey** — canonical molecular name (hash-like).
- **CIF** (IUCr) — crystallography; heavy but universal.
- **extxyz / POSCAR** — atomistics; minimalist.
- **CML** (Chemical Markup Language) — XML-based; has lost popularity.

## 1.2. Reaction networks — "programming like code"

### Antimony — the most readable

A text front-end for SBML, developed by the Sauro lab (U. Washington):
```antimony
J0: A -> B; k1*A
J1: B -> C; k2*B
k1 = 0.1; k2 = 0.5; A = 10
```
Antimony 3 (2024–2025) added FBC, Layout, annotations, and distributions.
**The closest to a "reads like a program" answer for CRN/dynamics.**

### Rule-based

- **BNGL** (BioNetGen Language, Faeder/Hlavacek) — rule-based for
  combinatorial spaces (signalling pathways, protein states).
- **Kappa** — a close analogue of BNGL, from a separate group (Danos/Krivine).
- Both are powerful but unreadable at scale. Antimony has a modular structure;
  Kappa does not, making large Kappa models hard to maintain.

### Kinetics

- **SBML** — XML under the hood, not meant for humans; Antimony is its text front-end.
- **Cantera YAML** (≥2.5) — gas-phase/catalytic kinetics, readable:
  reactions, thermodynamics, and transport in a single file.
- **MobsPy** (PLOS Comp Bio 2025) — Python DSL for biochemical reaction
  networks, object-oriented on top of the BNGL idea.

## 1.3. DFT / atomistics — no unified language

Each code has its own format: QE namelists, VASP INCAR, ABACUS INPUT,
GPAW Python, CP2K input sections, ORCA keyword lines. Unification attempts:

- **NOMAD Metainfo** (FAIRmat NFDI) — common schema with parsers for ~40 codes
  (QE, VASP, GPAW, CP2K, ABINIT, FHI-aims, ORCA, Gaussian, LAMMPS, GROMACS…).
  This is a **schema + parsers**, not a language you *write* input in — it is what
  your input is *converted into* for interoperability.
- **OPTIMADE** — query language for materials databases
  (`elements HAS "Fe" AND nelements=2`). Describes data, not calculations.
- **QCSchema** (MolSSI) — JSON schema for QM calculations (input/output/wfn).
  Used in QCArchive, Psi4, and the MolSSI stack.
- **ASE** (Atomic Simulation Environment) — Python as de facto DSL:
  `Atoms()`, `calc=Espresso(...)`, `MDLogger`, `NEB`. A single script reads
  identically regardless of backend (QE/VASP/GPAW). **In our project ASE is the primary "metalanguage."**
- **AiiDA** — workflow + provenance graph (every input/output node hashed,
  graph is reproducible). A *reproducibility metalanguage*, not a process description language.
- **atomate2 / Fireworks** — Python workflows on top of pymatgen.

## 1.4. Force fields

- **SMIRNOFF** (Open Force Field Initiative) — XML, explicitly readable:
  torsions described by SMARTS pattern + parameters. One file = one force field.

## 1.5. Experiment / laboratory

- **ISA-Tab / ISA-JSON** — investigation/study/assay structure.
- **ELN formats** (eLabFTW, RSpace) — schema-friendly notebooks.
- **NeXus / HDF5** — for neutron/synchrotron data.

## 1.6. Recent developments 2025–2026

1. **Antimony 3** — major update; now covers constraint-based modelling
   (FBA), distributions, and layout. Closest to a "program in a language"
   for chemical dynamics.
2. **MobsPy** — Python DSL for biochemical reaction networks,
   object-oriented on top of the BNGL idea.
3. **LangSim** (MPIE) — LLM front-end over atomistic simulation: write
   in plain English, an agent calls ASE/pyiron underneath. Not a metalanguage
   but a *natural-language interpreter into ASE*.
4. **Foundation models for atomistic simulation** (Nat Rev Chem 2025) —
   a review showing that the field is not converging on a unified language,
   but on unified *representations* (graph + species embeddings).

---

# Part 2. Inorganic / Materials Science

## 2.1. Crystal structure

- ⭐ **CIF** (IUCr standard) — text, but not directly human-friendly:
  space group, Wyckoff positions, ADP. Readable with practice.
- **magCIF** — CIF extension for magnetic structures
  (modulation vector, magnetic SG).
- **AFLOW prototype labels** — compact signature:
  `A2B_cF24_225_a_c` = composition + Pearson symbol + space group + Wyckoff letters.
  Closest to a "filename that tells you everything."
- **Wyckoff / Pearson / Strukturbericht** (B1, B2, C1…) — old but
  still alive in the literature.
- **POSCAR / extxyz** — for calculations; minimalist.

## 2.2. Defect chemistry — ⭐ a genuine DSL

**Kröger-Vink notation** — equations that function as code:
```
nil → V_M''  + V_X^••           (Schottky)
M_M^× + X_X^× → V_M''  + V_X^•• + M_i^•• + X_i''   (Frenkel)
2·Fe_Fe^× + ½ O₂(g) → 2·Fe_Fe^•  + V_Fe''  + O_O^×   (acceptor doping)
```
Written as a reaction equation using standard notation:
- superscript = charge relative to the ideal lattice
  (• positive, ' negative, × neutral),
- subscript = site.

**90% readable after one page of a textbook.** No official ASCII standard exists,
but `pymatgen.analysis.defects` and `doped` (Walsh group, 2024) encode this
in Python objects.

## 2.3. Surfaces

- **Wood notation**: `(2×2)R45°`, `c(4×2)` — for commensurate reconstructions.
- **Matrix notation** — for incommensurate: $\binom{2 \, 1}{-1 \, 2}$.
- **ASE slab API** — Python DSL: `surface(bulk, indices=(1,1,1), layers=4, vacuum=15)`
  reads like a function call.

## 2.4. Magnetic structure

- **magCIF** + **MAGNDATA** (Bilbao Crystallographic Server) — a genuine DSL
  for magnetic structures: propagation vector `k=(0,0,1/2)`,
  irreducible representations, magnetic space groups (Belov-Neronova-Smirnova).
- **Mantid scripting** — for neutron data.

## 2.5. Phase thermodynamics — ⭐ a genuine DSL

**CALPHAD TDB format** (Thermo-Calc, OpenCalphad, pycalphad, ESPEI) —
text-based databases:
```tdb
PHASE LIQUID:L %  1  1.0 !
CONSTITUENT LIQUID:L : FE,S : !
PARAMETER G(LIQUID,FE;0)  298.15  GFEL;  6000 N !
PARAMETER L(LIQUID,FE,S;0)  298.15  -104888.7+0.338*T;  6000 N !
```
Compound Energy Formalism — a real program in a DSL for
thermodynamic modelling. Recent (2025): coupling with MLIPs (MACE-MP / UMA)
for automatic parameter fitting. For our Fe-S, Ni-S context, the CALPHAD
databases `SGTE PURE5` + `SSUB` already contain FeS, FeS₂, Fe₃S₄.

## 2.6. Aqueous / hydrothermal systems — ⭐⭐ relevant to our project

**PHREEQC input** (USGS) — already installed (`phreeqpython`).
A pure KEYWORD-DSL with balanced chemical equations:
```phreeqc
SOLUTION 1
    pH 6.5
    temp 90
    Fe(2) 1.0e-3
    S(-2) 5.0e-4
SOLUTION_SPECIES
    Fe+2 + HS- = FeHS+ ; log_k 5.30
PHASES
    Mackinawite
    FeS + H+ = Fe+2 + HS- ; log_k -3.6
KINETICS
    Pyrite_oxidation
    -m0  1e-6
    -formula  FeS2 + 3.5 H2O + 1.75 O2 = Fe(OH)3 + 2 SO4-2 + 4 H+
RATES
    Pyrite_oxidation
    -start
    10  rate = parm(1) * (m/m0)^0.67 * act("O2")^0.5
    20  save rate * time
    -end
```
One file = complete model: speciation + minerals + kinetics + transport.
**Close to ideal for our purposes.**

Alternatives (same class, different flavour):
- **GWB** (Geochemists Workbench) — commercial, but similar text DSL.
- **EQ3/6** (LLNL).
- **CHNOSZ** (R) — less DSL, more API.
- **Cantera YAML with surface kinetics** (≥3.0) — gas + electrochemical surface,
  close to our sulfide electrode context; lacks full aqueous speciation.

## 2.7. Databases and queries

- **OPTIMADE 1.x** — unified query DSL over Materials Project, AFLOW,
  OQMD, NOMAD, JARVIS, COD, Materials Cloud:
  ```
  elements HAS ALL "Fe","S" AND nelements=2 AND _mp_band_gap<0.1
  ```
- **Materials Project schema** — Pydantic models, readable as typed Python.
- **NOMAD Metainfo** — common schema for DFT results, parsers for ~40 codes.

## 2.8. Force fields / MLIP

- **OpenKIM API** — standard interface for classical potentials.
- **MACE / CHGNet / SevenNet / UMA / MatterSim** — not DSLs, but all share
  the **`extxyz` format** + OpenKIM-style metadata.
  For foundation MLIPs this is the de facto data-transfer language
  (energy/forces/stress in comments).
- **SMIRNOFF** — formally for organics, but Open Force Field is expanding
  to metal centres (2025).

## 2.9. Mineralogy

- **IMA mineral list** — names, not a language.
- **End-member formula syntax** (Berman, Helgeson notation) — for mineral thermodynamics.

## 2.10. Generative / LLM-friendly (2024–2026)

- **CrystaLLM** (Antunes et al., Nat Commun 2024) — GPT-style LM on CIF:
  provide composition + space group, receive a complete CIF.
  Perovskites/spinels/zeolites/MOFs.
- **CrystalTextLLM** (Meta) — Llama-2-70B fine-tuned on textual
  point-cloud descriptions.
- **CrysText** — combination of CIF + Llama 3.1-8B + QLoRA.
- **Robocrystallographer** (Materials Project) — inverse direction:
  CIF → readable English description ("face-sharing octahedra…").
- **Generative AI for crystals review** (npj Comp Mat 2025) — review of the entire field.
- **MatSci-LLM-Agents** — agentic framework for materials science.

---

# Sources

## Part 1 (generic / organic)

- [An Update to the SBML Human-Readable Antimony Language (arXiv 2405.15109)](https://arxiv.org/abs/2405.15109)
- [Antimony 3: Extending human-readable model definitions (bioRxiv 2026)](https://www.biorxiv.org/content/10.64898/2026.04.07.717118v1)
- [MobsPy: A programming language for biochemical reaction networks (PLOS Comp Bio 2025)](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1013024)
- [Antimony Reference (Tellurium docs)](https://tellurium.readthedocs.io/en/latest/antimony.html)
- [A High-Level Language for Rule-Based Modelling — Kappa (PLOS One)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0114296)
- [NOMAD Metainfo docs](https://nomad-lab.eu/prod/v1/docs/examples/computational_data/metainfo.html)
- [FAIRmat custom workflows tutorial](https://fairmat-nfdi.github.io/fairmat-tutorial-14-computational-plugins/custom_workflows/)
- [LangSim — LLM Interface for Atomistic Simulation (MPIE)](https://www.mpie.de/5063016/LangSim)
- [Foundation models for atomistic simulation of chemistry and materials (Nat Rev Chem 2025)](https://www.nature.com/articles/s41570-025-00793-5)
- [32 examples of LLM applications in materials & chemistry (IOP 2025)](https://iopscience.iop.org/article/10.1088/2632-2153/ae011a)
- [General-Purpose Models for the Chemical Sciences (Chem Reviews 2025)](https://pubs.acs.org/doi/10.1021/acs.chemrev.5c00583)
- [LLM-guided automated reaction pathway exploration (Comm Chem 2025)](https://www.nature.com/articles/s42004-025-01630-y)
- [A multimodal LLM for materials science (Nat Mach Intell 2026)](https://www.nature.com/articles/s42256-026-01214-y)

## Part 2 (inorganic / materials science)

- [The CALPHAD method and its role in material development (PMC 4912057)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4912057/)
- [CALPHAD + MLIP — Pt-W system case study (arXiv 2508.01028)](https://arxiv.org/html/2508.01028v1)
- [Accelerating CALPHAD with universal MLIPs (arXiv 2411.15351)](https://arxiv.org/html/2411.15351v1)
- [PHREEQC Version 3 (USGS)](https://www.usgs.gov/software/phreeqc-version-3)
- [PHREEQC v3 input description (USGS TM 6-A43)](https://pubs.usgs.gov/tm/06/a43/pdf/tm6-A43.pdf)
- [Crystal structure generation with autoregressive LLM — CrystaLLM (Nat Commun 2024)](https://www.nature.com/articles/s41467-024-54639-7)
- [CrystaLLM repository (lantunes)](https://github.com/lantunes/CrystaLLM)
- [Crystal-text-LLM (Meta Research)](https://github.com/facebookresearch/crystal-text-llm)
- [Generative AI for crystal structures — review (npj Comp Mat 2025)](https://www.nature.com/articles/s41524-025-01881-2)
- [LLMs Are Innate Crystal Structure Generators (Cornell 2025)](https://www.cs.cornell.edu/gomes/pdf/2025_gan_arxiv_matllmsearch.pdf)
- [A survey of AI-supported materials informatics (ScienceDirect 2025)](https://www.sciencedirect.com/science/article/pii/S1574013725001212)
- [MatSci-LLM-Agents (GitHub)](https://github.com/cakshat/MatSci-LLM-Agents)

## Additional (not from search, widely known)

- IUCr CIF dictionary — `iucr.org/resources/cif`
- AFLOW Prototype Encyclopedia — `aflowlib.org/prototype-encyclopedia`
- Bilbao Crystallographic Server / MAGNDATA — `cryst.ehu.es`
- pymatgen — `pymatgen.org`
- ASE — `ase-lib.org` (was `wiki.fysik.dtu.dk/ase`)
- AiiDA — `aiida.net`
- OpenKIM — `openkim.org`
- Open Force Field Initiative / SMIRNOFF — `openforcefield.org`
