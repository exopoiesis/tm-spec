# JSON Schemas

Each TM-Spec specification version ships a single JSONSchema 2020-12
file in this directory. The version embedded inside each YAML document's
`spec:` field MUST match a schema filename here.

| Schema file | Spec version | Status | Notes |
|-------------|--------------|--------|-------|
| `0.1.json` | `tm-spec/0.1` | DRAFT | 11 kinds; 22 design decisions D-01..D-22 |

## Resolving by URL

The canonical hosting URL is `https://exopoiesis.github.io/tm-spec/<v>.json`.
Each schema's `$id` field declares the URL, so JSON Schema validators
that follow `$id` resolve correctly against the published copy.

## Bundled inside the package

A duplicate copy lives at `src/tm_spec/schemas/0.1.json` so that
`pip install tm-spec` makes the schema available offline. The two files
are kept identical by `tests/test_schema_self.py::test_bundled_copy_matches`.

## Validating

```bash
pip install tm-spec
tm-spec validate examples/pyr_smoke.tm.yaml
# or
python -m jsonschema -i examples/pyr_smoke.tm.yaml schemas/0.1.json
```
