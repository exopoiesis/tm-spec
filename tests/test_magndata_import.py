"""Tests for tm_spec.importers.magndata (MAGNDATA experimental magnetic anchor).

Fully offline: the LaMnO3 fixture (real MAGNDATA entry 0.1) + synthetic minimal
magCIFs exercise the parser, the symmetry-based FM/AFM classifier, and the
tm-spec mapping. No network.
"""
from __future__ import annotations

from pathlib import Path

from tm_spec import validate_doc
from tm_spec.importers.magndata import (
    _axial_projector,
    _net_moment_ratio,
    _symop_rotation_theta,
    magcif_to_tm_spec,
    net_moment_allowed,
    parse_magcif,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "magndata_0.1_LaMnO3.mcif"

# A minimal synthetic magCIF: single moment, identity-only symmetry -> pure FM.
_FM_MCIF = """data_test
_chemical_formula_sum 'Fe'
_space_group_magn.number_BNS 1.1
_space_group_magn.name_BNS "P1"
_space_group_magn.point_group_name "1"
_cell_length_a 3.0
_cell_length_b 3.0
_cell_length_c 3.0
_cell_angle_alpha 90.0
_cell_angle_beta 90.0
_cell_angle_gamma 90.0
loop_
_space_group_symop_magn_operation.id
_space_group_symop_magn_operation.xyz
1 x,y,z,+1
loop_
_atom_site_moment.label
_atom_site_moment.crystalaxis_x
_atom_site_moment.crystalaxis_y
_atom_site_moment.crystalaxis_z
_atom_site_moment.symmform
Fe 3.0 0.0 0.0 mx,my,mz
"""

# Identity + a pure time-reversal operation -> net moment forced to zero -> AFM.
_AFM_MCIF = _FM_MCIF.replace("1 x,y,z,+1\n", "1 x,y,z,+1\n2 x,y,z,-1\n")


def test_symop_rotation_theta_parsing():
    R, theta = _symop_rotation_theta("x+1/2,-y+1/2,-z+1/2,-1")
    assert R == [[1, 0, 0], [0, -1, 0], [0, 0, -1]]
    assert theta == -1
    R2, t2 = _symop_rotation_theta("x,y,z,+1")
    assert R2 == [[1, 0, 0], [0, 1, 0], [0, 0, 1]] and t2 == 1


def test_parse_lamno3_fixture():
    p = parse_magcif(FIX.read_text(encoding="utf-8"))
    assert p["formula"] == "LaMnO3"
    assert p["bns_number"] == "62.448"
    assert p["bns_name"] == "Pn'ma'"
    assert p["point_group"] == "m'm'm"
    assert p["propagation_vectors"] == [[0.0, 0.0, 0.0]]
    assert len(p["symops"]) == 8
    assert p["moments"] == [{"label": "Mn", "mx": 3.87, "my": 0.0, "mz": 0.0}]


def test_lamno3_classified_AFM_and_valid():
    # LaMnO3 entry 0.1: A-type AFM (moment on the symmetry-cancelled axis) -> AFM-G,
    # even though the m'm'm symmetry permits a weak-FM canting (rank(P) > 0).
    doc = magcif_to_tm_spec(FIX.read_text(encoding="utf-8"), code="0.1")
    assert net_moment_allowed(parse_magcif(FIX.read_text(encoding="utf-8"))["symops"]) is True
    assert doc["magnetic"]["state"] == "AFM-G"
    assert doc["magnetic"]["bns_group"] == "Pn'ma'"
    assert doc["magnetic"]["magmoms_uB"] == {"Mn": 3.87}
    assert doc["structure"]["geometry_origin"] == "experimental"
    assert doc["provenance"]["import_source"]["entry_id"] == "magndata:0.1"
    errs, rules = validate_doc(doc)
    assert errs == [], errs
    assert [m for lv, m in rules if lv == "error"] == []


def test_synthetic_fm():
    doc = magcif_to_tm_spec(_FM_MCIF, code="test-fm")
    assert _net_moment_ratio(parse_magcif(_FM_MCIF)["symops"], (3.0, 0.0, 0.0)) == 1.0
    assert doc["magnetic"]["state"] == "FM"
    assert validate_doc(doc)[0] == []


def test_synthetic_afm_via_time_reversal():
    p = parse_magcif(_AFM_MCIF)
    assert len(p["symops"]) == 2
    # identity + pure time reversal -> projector is zero -> net moment forbidden.
    assert net_moment_allowed(p["symops"]) is False
    assert _net_moment_ratio(p["symops"], (3.0, 0.0, 0.0)) == 0.0
    doc = magcif_to_tm_spec(_AFM_MCIF, code="test-afm")
    assert doc["magnetic"]["state"] == "AFM-G"
    assert validate_doc(doc)[0] == []


def test_formula_fallback_from_atom_sites():
    # No _chemical_formula_sum -> derive from _atom_site_type_symbol (Co P S2 thiophosphate).
    mcif = (
        "data_t\n_space_group_magn.name_BNS \"P1\"\n_space_group_magn.point_group_name \"1\"\n"
        "_cell_angle_alpha 90.0\n_cell_angle_beta 90.0\n_cell_angle_gamma 90.0\n"
        "loop_\n_space_group_symop_magn_operation.id\n_space_group_symop_magn_operation.xyz\n1 x,y,z,+1\n"
        "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n_atom_site_fract_z\n"
        "Co1 Co 0.0 0.33 0.0\nP1 P 0.05 0.0 0.16\nS1 S 0.74 0.0 0.24\nS2 S 0.25 0.16 0.24\n"
        "loop_\n_atom_site_moment.label\n_atom_site_moment.crystalaxis_x\n_atom_site_moment.crystalaxis_y\n"
        "_atom_site_moment.crystalaxis_z\nCo1 2.5 0.0 0.0\n"
    )
    p = parse_magcif(mcif)
    assert p.get("formula") is None  # no _chemical_formula_sum line
    assert p["site_elements"] == {"Co": 1, "P": 1, "S": 2}
    doc = magcif_to_tm_spec(mcif, code="t")
    assert doc["structure"]["formula"] == "CoPS2"  # Hill-ish, asymmetric-unit
    assert doc["structure"]["formula"] != "Unknown"


def test_lamno3_uses_formula_sum_not_fallback():
    # When _chemical_formula_sum IS present, it wins over the site fallback.
    p = parse_magcif(FIX.read_text(encoding="utf-8"))
    assert p["formula"] == "LaMnO3"


def test_projector_rank():
    # identity-only -> projector is identity -> rank 3 (net moment free).
    P = _axial_projector(["x,y,z,+1"])
    from tm_spec.importers.magndata import _rank3
    assert _rank3(P) == 3
