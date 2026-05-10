---
title: TM-Spec — Third Matter Specification
description: Declarative YAML metalanguage for DFT/MLIP/MD calculations with sanity gates, provenance, and code-agnostic level-of-theory.
---

# TM-Spec

**Third Matter Specification** — a declarative YAML/JSONL metalanguage and
reference toolchain for describing structures, defects, magnetic state,
environment, reaction networks, DFT/MLIP calculations, workflows,
sanity gates, and provenance of atomistic simulations.

> Status: **v0.1 (draft)** · License: **MIT** (code) + **CC-BY-4.0** (spec)
>
> Source: [github.com/exopoiesis/tm-spec](https://github.com/exopoiesis/tm-spec) ·
> JSON Schema: [`/0.1.json`](./0.1.json)

---

## What is it

One YAML file per calculation, schema-validated, exportable to FAIR
archives (NOMAD), with first-class **sanity gates** compiled from real
project lessons-learned. Aligned with NOMAD Metainfo, OPTIMADE 1.3,
QCSchema, magCIF, AFLOW, AiiDA, Antimony 3, PHREEQC v3,
pymatgen-defects, MACE/CHGNet.

Designed for three niches that mainstream workflow managers
(AiiDA, atomate2) do not own:

1. **Paper SI format** — reviewers read one YAML in any text editor; no
   AiiDA install required.
2. **Ephemeral cloud compute** — no daemon, no DB; YAML in, executable
   script out.
3. **Domain-specific recipes** — Fe-S minerals today, extensible to
   oxides, MOFs, perovskites tomorrow.

---

## Specification (v0.1)

| Document | What it covers |
|----------|---------------|
| [Specification text](specification/v0.1) | Section-by-section spec with examples (header, structure, defects, magnetic, environment, reactions, calculation, workflow, results, sanity, provenance). |
| [JSON Schema](0.1.json) | Machine-readable schema (Draft 2020-12). Resolves at `https://exopoiesis.github.io/tm-spec/0.1.json`. |
| [Design decisions](design-decisions) | Decision log D-01..D-22 with rationale, sources, and breaking-change flags. |
| [Standards alignment](standards-alignment) | Field-by-field mapping to 11 parent standards. |
| [Landscape](landscape) | Strategic positioning vs AiiDA / atomate2 / FireWorks / CWL / Snakemake / NOMAD inputs. |
| [Literature review](lit-review) | Survey of related metalanguages (generic + organic + materials). |

---

## Quickstart

```bash
pip install tm-spec
tm-spec validate examples/pyr_smoke.tm.yaml
```

Or validate a document against the schema directly:

```bash
python -m jsonschema -i my.tm.yaml https://exopoiesis.github.io/tm-spec/0.1.json
```

See the [README on GitHub](https://github.com/exopoiesis/tm-spec/#readme)
for full toolchain (`extract`, `lint`, `sanity-fill`, `export-nomad`).

---

## Citation

If TM-Spec helps your paper SI, please cite:

> Morozov, I. (2026). *TM-Spec: a declarative YAML metalanguage for
> reproducible atomistic calculations.* Version 0.1.
> [github.com/exopoiesis/tm-spec](https://github.com/exopoiesis/tm-spec)

A `CITATION.cff` file is in the repository root.
