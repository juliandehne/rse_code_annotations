"""Responsible RSE, question 1: *may the code and its data be reused -- and found again?*"""

from __future__ import annotations

from ._stub import ResponsibleRSEStub


class LicenceComplianceAnalyzer(ResponsibleRSEStub):
    """TODO (Tier A, S–M): is the project's licence consistent with what it uses?

    Detect:
      * files without ``SPDX-License-Identifier`` / copyright header (REUSE spec);
      * missing or non-SPDX project licence (FAIR4RS R1.1);
      * outbound licence incompatible with (a) declared dependencies, (b) vendored /
        copied code, (c) bundled ``@external_tool`` binaries.
    Example finding: ``fail pyproject: MIT outbound, depends on GPL-3.0-only 'foo'``.
    Tools: ``reuse lint`` (call as subprocess, GPL), ``license-expression`` to parse SPDX
    expressions, optionally ``scancode-toolkit``; a small compatibility table.
    Suggested base: plain ``Analyzer`` (works on the project tree, not on functions).
    Difficulty: 3/5 (~3 h/week) -- REUSE and SPDX parsing are off the shelf, but resolving
      dependency licences and a defensible compatibility table (OSADL matrix, CC-BY-4.0)
      take design and many test fixtures.
    EVERSE: indicators ``software_has_license``, ``software_has_license_for_file_types``
      (FAIRness); RSQKit https://everse.software/RSQKit/licensing_software ; resqui's
      HowFairIs / RSFC plugins only check presence.
    """

    name = "licence"
    description = "licence presence and compatibility with dependencies / vendored code"
    tier, effort, proposal = "A", "S–M", "RESPONSIBLE_RSE_PLUGINS.md §2.1"
    difficulty = 3
    hooks = ("project", "@external_tool")
    tools = ("reuse", "license-expression", "scancode-toolkit")


class DataTermsAnalyzer(ResponsibleRSEStub):
    """TODO (Tier A, M): are the data used and published under terms that allow it?

    Inbound: every ``@data_input`` / ``@human_input`` declares ``source=``, ``license=``
    and, for data about people, ``consent=`` / ``legal_basis=``. Flag missing terms,
    licences that forbid the use (NC, ND, "research only" re-published), and scraping
    (``requests`` / ``BeautifulSoup`` in a ``@data_input``) without a ToS note.
    Outbound: a published ``@data_output`` needs a datasheet / data statement / Croissant
    file with RAI fields; a saved model needs a model card. Propagate the most
    restrictive input licence to each output along the call graph (like hazards).
    Tools: ``mlcroissant``, ``huggingface_hub.ModelCard``.
    Difficulty: 3/5 (~3 h/week) -- new decorator kwargs, licence propagation over the call
      graph and Croissant / model-card validation; each part is small, together they need
      design.
    EVERSE: no data-licence indicator (a gap on their side); closest are
      ``descriptive_metadata`` and RSQKit https://everse.software/RSQKit/fair_rs /
      https://everse.software/RSQKit/software_metadata .
    """

    name = "data_terms"
    description = "data licences, consent and datasheets / model cards for outputs"
    tier, effort, proposal = "A", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.6"
    difficulty = 3
    hooks = ("@data_input", "@human_input", "@data_output")
    tools = ("mlcroissant", "huggingface_hub")


class ArchivalSustainabilityAnalyzer(ResponsibleRSEStub):
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
    when = "static"
    tier, effort, proposal = "C", "S–M", "RESPONSIBLE_RSE_PLUGINS.md §2.13"
    difficulty = 3
    hooks = ("project", "@external_tool")
    tools = ("swh.model", "truckfactor", "OpenSSF Scorecard")
