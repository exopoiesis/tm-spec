---
title: TM-Spec — Third Matter Specification
description: Declarative YAML metalanguage for DFT/MLIP/MD calculations with sanity gates, provenance, and NOMAD import/export.
---

# TM-Spec

**Third Matter Specification** is a declarative YAML/JSONL metalanguage
and reference toolchain for describing atomistic simulations:
structures, defects, magnetic state, environment, reactions,
DFT/MLIP/MD calculations, workflows, sanity gates, results, and
provenance.

> Status: **v0.2 (draft)** · Package: **0.2.0** · License: **MIT** (code) +
> **CC-BY-4.0** (spec)
>
> Source: [github.com/exopoiesis/tm-spec](https://github.com/exopoiesis/tm-spec) ·
> JSON Schema: [`/0.2.json`](./0.2.json)

---

## What is it

One YAML file per calculation, schema-validated, exportable to FAIR
archives, with first-class **sanity gates** compiled from real project
lessons-learned. v0.2 adds:

- `SinglePointCalculation` for single SCF/electronic-structure results.
- `RelaxCalculation` for geometry optimisations.
- `tm-spec import-nomad` and `import-nomad-batch` for public NOMAD
  Archive entries.

Designed for niches that mainstream workflow managers do not own:

1. **Paper SI format** — reviewers read one YAML in any text editor.
2. **Ephemeral cloud compute** — no daemon, no DB; YAML in, artefacts out.
3. **Domain-specific recipes** — Fe-S minerals today, extensible later.

---

## Specification

| Document | What it covers |
|----------|---------------|
| [v0.2 specification](specification/v0.2) | Current draft: v0.1 core plus SinglePoint/Relax and NOMAD import provenance. |
| [v0.2 JSON Schema](0.2.json) | Machine-readable schema (Draft 2020-12). Resolves at `https://exopoiesis.github.io/tm-spec/0.2.json`. |
| [v0.1 specification](specification/v0.1) | Legacy initial draft retained for old documents. |
| [Design decisions](design-decisions) | Decision log D-01..D-25 with rationale, sources, and breaking-change flags. |
| [Standards alignment](standards-alignment) | Field-by-field mapping to parent standards. |
| [Landscape](landscape) | Strategic positioning vs AiiDA / atomate2 / FireWorks / CWL / Snakemake. |
| [Literature review](lit-review) | Survey of related metalanguages. |

---

## Quickstart

```bash
pip install tm-spec
tm-spec validate examples/pyr_smoke.tm.yaml
tm-spec import-nomad <entry_id> --out imported.tm.yaml
```

Validate directly against the published schema:

```bash
python -m jsonschema -i my.tm.yaml https://exopoiesis.github.io/tm-spec/0.2.json
```

See the [README on GitHub](https://github.com/exopoiesis/tm-spec/#readme)
for the full toolchain.

---

## Citation

If TM-Spec helps your paper SI, cite:

> Morozov, I. (2026). *TM-Spec: a declarative YAML metalanguage for
> reproducible atomistic calculations.* Version 0.2.
> [github.com/exopoiesis/tm-spec](https://github.com/exopoiesis/tm-spec)

A `CITATION.cff` file is in the repository root.
