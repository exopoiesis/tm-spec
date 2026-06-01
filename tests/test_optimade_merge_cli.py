"""End-to-end test for ``tm-spec import-optimade --merge``.

The integration: an OPTIMADE structure hit (network stubbed, offline-synthetic)
is folded into a locally-stored NOMAD-imported base doc, and the merged result
must validate against schema 0.3 — all without touching the network or the
filesystem beyond a tmp dir.
"""
from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import yaml

from tm_spec import load_doc, validate_doc
from tm_spec.importers import optimade as opt

NOMAD_BASE: dict[str, Any] = {
    "spec": "tm-spec/0.3",
    "kind": "SinglePointCalculation",
    "id": "tm.nomad.fes_sp_0001.2026-06-01",
    "schema_url": "https://exopoiesis.github.io/tm-spec/0.3.json",
    "structure": {"formula": "Fe2S4", "geometry_origin": "dft_static"},
    "calculation": {
        "method": "DFT",
        "level": {"xc": "PBE", "spin": "collinear"},
        "code": {"name": "QuantumESPRESSO", "version": "7.3.1"},
    },
    "magnetic": {"state": "FM", "collinear": True},
    "results": {"status": "PRELIMINARY", "paper_quotable": False, "energy_eV": -123.4},
    "sanity": [{"id": "G05_scf_converged", "rule": "scf converged", "pass": True}],
    "provenance": {
        "date": "2026-06-01",
        "author": "import@nomad",
        "import_source": {"archive": "nomad", "entry_id": "fes_sp_0001"},
        "compute": {"host": "nomad-archive", "cost_usd": 0.0},
    },
}

OPTIMADE_PAYLOAD: dict[str, Any] = {
    "data": [
        {
            "id": "mp-1522",
            "type": "structures",
            "attributes": {
                "chemical_formula_descriptive": "Fe2S4",
                "chemical_formula_reduced": "FeS2",
                "chemical_formula_anonymous": "AB2",
                "lattice_vectors": [
                    [5.42, 0.0, 0.0],
                    [0.0, 5.42, 0.0],
                    [0.0, 0.0, 5.42],
                ],
                "dimension_types": [1, 1, 1],
                "structure_features": [],
                "last_modified": "2025-11-02T08:30:00Z",
            },
        }
    ],
}


def test_import_optimade_merge_end_to_end(tmp_path: Path, monkeypatch) -> None:
    from tm_spec import cli

    base_path = tmp_path / "nomad_base.tm.yaml"
    base_path.write_text(yaml.safe_dump(NOMAD_BASE, sort_keys=False), encoding="utf-8")
    out_path = tmp_path / "merged.tm.yaml"

    # Stub the HTTP GET so the live path returns our synthetic OPTIMADE payload.
    monkeypatch.setattr(opt, "_http_get_json", lambda url, params, timeout: OPTIMADE_PAYLOAD)

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main(
            [
                "import-optimade",
                "--reduced-formula", "FeS2",
                "--provider", "mp",
                "--merge", str(base_path),
                "--out", str(out_path),
            ]
        )
    assert rc == 0, err.getvalue()
    assert out_path.exists()

    docs = load_doc(out_path)
    assert len(docs) == 1
    merged = docs[0]

    # NOMAD depth kept.
    assert merged["calculation"]["level"]["xc"] == "PBE"
    assert merged["magnetic"]["state"] == "FM"
    assert merged["results"]["energy_eV"] == -123.4
    # OPTIMADE width filled.
    assert "lattice_vectors_A" in merged["structure"]
    assert merged["structure"]["chemical_formula_reduced"] == "FeS2"
    # Both import sources recorded.
    isrc = merged["provenance"]["import_source"]
    assert isinstance(isrc, list)
    assert {s["archive"] for s in isrc} == {"nomad", "materials_project"}

    # Merged doc validates.
    schema_errs, rule_issues = validate_doc(merged)
    assert not schema_errs, schema_errs
    assert not [m for level, m in rule_issues if level == "error"], rule_issues


def test_import_optimade_merge_material_mismatch_fails(tmp_path: Path, monkeypatch) -> None:
    """A merge into a base of a different material must FAIL (exit 2) by default."""
    from tm_spec import cli

    base = dict(NOMAD_BASE)
    base = {**NOMAD_BASE, "structure": {"formula": "CuO", "geometry_origin": "dft_static"}}
    base_path = tmp_path / "cuo_base.tm.yaml"
    base_path.write_text(yaml.safe_dump(base, sort_keys=False), encoding="utf-8")

    monkeypatch.setattr(opt, "_http_get_json", lambda url, params, timeout: OPTIMADE_PAYLOAD)

    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        rc = cli.main(
            [
                "import-optimade",
                "--reduced-formula", "FeS2",
                "--merge", str(base_path),
            ]
        )
    assert rc == 2
    assert "MATERIAL_MISMATCH" in err.getvalue()
