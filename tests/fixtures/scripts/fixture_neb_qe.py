"""Synthetic ASE/QE NEB script for the tm-spec test suite.

Mimics the shape of a canonical NEB script in the Third Matter project:
argparse defaults, a ``crystal()`` builder, ``Espresso`` calculator with
a nested ``input_data`` dict, ``NEB`` + ``BFGS`` + ``FIRE``. The script
is never executed; the test suite only feeds it to ``ast.parse``.

If the AST extractor regresses, ``test_extract.py`` will fail.
"""
from __future__ import annotations

import argparse


def build_pyrite(repeat=(2, 2, 2)):
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ecutwfc",       default=60)
    parser.add_argument("--ecutrho",       default=240)
    parser.add_argument("--kpts",          default=[2, 2, 2])
    parser.add_argument("--mpi-np",        default=1)
    parser.add_argument("--n-images",      default=7)
    parser.add_argument("--k-spring",      default=0.10)
    parser.add_argument("--fmax-endpoint", default=0.05)
    parser.add_argument("--fmax-neb",      default=0.05)
    parser.add_argument("--idpp-prewrap",  default=True, action="store_true")
    parser.add_argument("--pseudo-dir",    default="/opt/pp/oncv_pbe")
    args = parser.parse_args()

    # Imports below are fake — never executed; only AST-parsed.
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
            "control": {"calculation": "relax"},
            "system":  {
                "ecutwfc":     args.ecutwfc,
                "ecutrho":     args.ecutrho,
                "occupations": "smearing",
                "smearing":    "gaussian",
                "degauss":     0.005,
                "nspin":       1,
            },
            "electrons": {"conv_thr": 1.0e-8, "mixing_mode": "plain"},
        },
    )
    atoms.calc = calc

    BFGS(atoms).run(fmax=args.fmax_endpoint)
    neb = NEB(images=[atoms] * args.n_images, k=args.k_spring, climb=True)
    FIRE(neb).run(fmax=args.fmax_neb)


if __name__ == "__main__":
    main()
