# TM-Spec — Specification

The current specification is **TM-Spec v0.3** (draft, 2026-06-01).

- **Current versioned text:** [`docs/specification/v0.3.md`](docs/specification/v0.3.md)
- **Current JSON Schema:** [`schemas/0.3.json`](schemas/0.3.json)
- **Legacy v0.2 text:** [`docs/specification/v0.2.md`](docs/specification/v0.2.md)
- **Legacy v0.2 schema:** [`schemas/0.2.json`](schemas/0.2.json)
- **Legacy v0.1 text:** [`docs/specification/v0.1.md`](docs/specification/v0.1.md)
- **Legacy v0.1 schema:** [`schemas/0.1.json`](schemas/0.1.json)
- **Sanity gate registry:** [`docs/gate-registry.md`](docs/gate-registry.md)
- **Design decisions:** [`docs/design-decisions.md`](docs/design-decisions.md)
- **Standards alignment:** [`docs/standards-alignment.md`](docs/standards-alignment.md)
- **Strategic landscape:** [`docs/landscape.md`](docs/landscape.md)
- **Literature review:** [`docs/lit-review.md`](docs/lit-review.md)

Each YAML/JSONL document declares its specification version in the
`spec:` field, e.g. `spec: tm-spec/0.3`. Validators MUST select the
schema from that field and MUST refuse documents whose version is not
supported by the implementation.

> Specification text and JSON Schema are licensed under **CC-BY-4.0**
> (see `LICENSES/CC-BY-4.0.txt`). The reference implementation in
> `src/` is licensed under **MIT** (see `LICENSE` and `LICENSES/MIT.txt`).
