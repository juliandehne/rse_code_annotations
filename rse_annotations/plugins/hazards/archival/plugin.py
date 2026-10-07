"""Hazard plugin ``archival`` -- a stub for students to implement.

Responsible RSE, question 1: *may the code and its data be reused -- and found again?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from ....core.plugin import Phase
from .._stub import HazardStub


class ArchivalSustainability(HazardStub):
    """TODO (Tier C, S–M): does the citation identify the code that produced the results?

    Offline: compute the SWHID of the tree (``swh identify``); compare ``CITATION.cff``
    ``version`` / ``date-released`` with the latest git tag; flag a dirty tree at release;
    truck factor from ``git log``. CI only (network): is the SWHID archived on Software
    Heritage, does the DOI resolve to the same version, OpenSSF Scorecard.
    Also runs in ``ci``; FAIR4RS F1 / A1 / R1.2.
    Difficulty: 3/5 (~3 h/week) -- several independent sub-checks (SWHID, CFF vs tag,
      truck factor) plus network-only CI parts that need mocking in tests.
    EVERSE: indicators ``archived_in_software_heritage``,
      ``archived_in_scholarly_repository``, ``persistent_and_unique_identifier``,
      ``has_releases``, ``versioning_standards_use``, ``software_has_citation``,
      ``has_active_contributors``, ``project_is_active``; RSQKit
      https://everse.software/RSQKit/archiving_software ,
      https://everse.software/RSQKit/software_identifiers ; resqui's RSFC and
      OpenSSFScorecard plugins implement several of these (reuse or call them in ``ci``).
    """

    name = "archival"
    description = "citable, archived, identifiable release; maintenance risk"
    question = "may the code and its data be reused -- and found again?"
    when = Phase.STATIC
    tier, effort, proposal = "C", "S–M", "RESPONSIBLE_RSE_PLUGINS.md §2.13"
    difficulty = 3
    hooks = ("project", "@external_tool")
    tools = ("swh.model", "truckfactor", "OpenSSF Scorecard")
