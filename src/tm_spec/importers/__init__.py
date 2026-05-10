"""TM-Spec importers — adapters from external archives into TM-Spec docs.

Currently shipped:
    tm_spec.importers.nomad   — NOMAD Archive (https://nomad-lab.eu)

Planned:
    tm_spec.importers.materials_project   — Materials Project entries.
    tm_spec.importers.aflow                — AFLOW prototypes.

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

__all__ = ["NomadClient", "archive_to_tm_spec", "fetch_to_tm_spec"]
