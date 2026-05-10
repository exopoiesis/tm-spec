# TM-Spec — Specification

The current specification is **TM-Spec v0.1** (draft, 2026-05-09).

- **Versioned text:** [`docs/specification/v0.1.md`](docs/specification/v0.1.md)
- **JSON Schema:**     [`schemas/0.1.json`](schemas/0.1.json)
- **Design decisions:** [`docs/design-decisions.md`](docs/design-decisions.md)
- **Standards alignment:** [`docs/standards-alignment.md`](docs/standards-alignment.md)
- **Strategic landscape:** [`docs/landscape.md`](docs/landscape.md)
- **Literature review:** [`docs/lit-review.md`](docs/lit-review.md)

Each YAML/JSONL document declares its specification version in the
`spec:` field, e.g. `spec: tm-spec/0.1`. Validators MUST refuse documents
whose `spec:` value does not match a schema they can load.

> Specification text and JSON Schema are licensed under **CC-BY-4.0**
> (see `LICENSE-SPEC`). The reference implementation in `src/` is
> licensed under **MIT** (see `LICENSE`).
