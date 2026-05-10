# JSON Schemas

Each TM-Spec specification version ships a JSON Schema 2020-12 file in
this directory. The version embedded inside each YAML document's `spec:`
field MUST match a schema filename here.

| Schema file | Spec version | Status | Notes |
|-------------|--------------|--------|-------|
| `0.1.json` | `tm-spec/0.1` | DRAFT legacy | Initial 11 kinds; 22 decisions D-01..D-22 |
| `0.2.json` | `tm-spec/0.2` | DRAFT current | Adds `SinglePointCalculation`, `RelaxCalculation`, and NOMAD import provenance |

## Resolving by URL

The canonical hosting URL is `https://exopoiesis.github.io/tm-spec/<v>.json`.
Each schema's `$id` field declares the URL, so JSON Schema validators
that follow `$id` resolve correctly against the published copy.

## Bundled inside the package

Duplicate copies live at `src/tm_spec/schemas/<v>.json` so that
`pip install tm-spec` makes schemas available offline. Current schema
copies are kept identical by:

- `tests/test_schema_self.py::test_bundled_copy_matches_repo_copy`
- `tests/test_schema_self.py::test_pages_copy_matches_repo_copy`

The Pages mirror lives at `docs/<v>.json`.

## Validating

```bash
pip install tm-spec
tm-spec validate examples/pyr_smoke.tm.yaml
# or
python -m jsonschema -i examples/pyr_smoke.tm.yaml schemas/0.2.json
```
