"""Variant of ``fixture_neb_qe.py`` with deliberate parameter drift.

Used by ``test_lint.py::test_lint_detects_drift``: a pilot YAML claims
defaults from ``fixture_neb_qe.py`` (cutoff 60, k-mesh [2,2,2], 7 images),
but is paired with this script which has different defaults. The lint
tool must surface the mismatches.
"""
from __future__ import annotations

import argparse


def build_pyrite(repeat=(2, 2, 2)):
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ecutwfc",       default=80)        # drift: 80 vs 60
    parser.add_argument("--ecutrho",       default=320)       # drift: 320 vs 240
    parser.add_argument("--kpts",          default=[3, 3, 3]) # drift: [3,3,3] vs [2,2,2]
    parser.add_argument("--mpi-np",        default=1)
    parser.add_argument("--n-images",      default=9)         # drift: 9 vs 7
    parser.add_argument("--k-spring",      default=0.30)      # drift: 0.30 vs 0.10
    parser.add_argument("--fmax-endpoint", default=0.05)
    parser.add_argument("--fmax-neb",      default=0.05)
    parser.add_argument("--idpp-prewrap",  default=True, action="store_true")
    parser.add_argument("--pseudo-dir",    default="/opt/pp/oncv_pbe")
    args = parser.parse_args()

    from ase.spacegroup import crystal  # type: ignore[import-not-found]  # noqa: I001
    from ase.calculators.espresso import Espresso  # type: ignore[import-not-found]
    from ase.optimize import BFGS, FIRE  # type: ignore[import-not-found]
    from ase.neb import NEB  # type: ignore[import-not-found]

    atoms = crystal(
        symbols=["Fe", "S"],
        basis=[(0.0, 0.0, 0.0), (0.385, 0.385, 0.385)],
        spacegroup=205,
        cellpar=[5.418, 5.418, 5.418, 90, 90, 90],
    )
    atoms = atoms.repeat((2, 2, 2))

    calc = Espresso(
        pseudopotentials={"Fe": "Fe.upf", "S": "S.upf"},
        input_data={
            "system":    {"ecutwfc": args.ecutwfc, "ecutrho": args.ecutrho, "nspin": 1},
            "electrons": {"conv_thr": 1.0e-8},
        },
    )
    atoms.calc = calc
    BFGS(atoms).run(fmax=args.fmax_endpoint)
    neb = NEB(images=[atoms] * args.n_images, k=args.k_spring, climb=True)
    FIRE(neb).run(fmax=args.fmax_neb)


if __name__ == "__main__":
    main()
