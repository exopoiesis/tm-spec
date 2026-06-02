"""TM-Spec importers — adapters from external archives into TM-Spec docs.

Currently shipped:
    tm_spec.importers.nomad     — NOMAD Archive (https://nomad-lab.eu)
    tm_spec.importers.optimade  — OPTIMADE federation (MP/NOMAD/OQMD/...)
    tm_spec.importers.mp        — Materials Project computed magnetism (magnetic depth)

Planned:
    tm_spec.importers.aflow                — AFLOW prototypes.
    tm_spec.importers.magndata             — MAGNDATA experimental magnetic structures.

Each importer should expose two surfaces:

    archive_to_tm_spec(archive: dict, **opts) -> dict
        Pure transformation. No I/O. Tests load cached JSON fixtures and
        feed them to this function so the test suite stays offline.

    fetch_to_tm_spec(entry_id: str, **opts) -> dict
        Side-effecting wrapper that performs the network call(s) and then
        delegates to archive_to_tm_spec. Used by the CLI sub-commands.
"""
from __future__ import annotations

from .nomad import (
    NomadClient,
    archive_to_tm_spec,
    fetch_to_tm_spec,
)
from .mp import (
    MPClient,
    fetch_to_tm_spec as fetch_mp_to_tm_spec,
    summary_to_tm_spec,
)
from .magndata import (
    fetch_to_tm_spec as fetch_magndata_to_tm_spec,
    magcif_to_tm_spec,
    parse_magcif,
)

__all__ = [
    "NomadClient", "archive_to_tm_spec", "fetch_to_tm_spec",
    "MPClient", "summary_to_tm_spec", "fetch_mp_to_tm_spec",
    "parse_magcif", "magcif_to_tm_spec", "fetch_magndata_to_tm_spec",
]
