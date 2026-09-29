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
    """

    name = "licence"
    description = "licence presence and compatibility with dependencies / vendored code"
    tier, effort, proposal = "A", "S–M", "RESPONSIBLE_RSE_PLUGINS.md §2.1"
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
    """

    name = "data_terms"
    description = "data licences, consent and datasheets / model cards for outputs"
    tier, effort, proposal = "A", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.6"
    hooks = ("@data_input", "@human_input", "@data_output")
    tools = ("mlcroissant", "huggingface_hub")


class ArchivalSustainabilityAnalyzer(ResponsibleRSEStub):
    """TODO (Tier C, S–M): does the citation identify the code that produced the results?

    Offline: compute the SWHID of the tree (``swh identify``); compare ``CITATION.cff``
    ``version`` / ``date-released`` with the latest git tag; flag a dirty tree at release;
    truck factor from ``git log``. CI only (network): is the SWHID archived on Software
    Heritage, does the DOI resolve to the same version, OpenSSF Scorecard.
    Also runs in ``ci``; FAIR4RS F1 / A1 / R1.2.
    """

    name = "archival"
    description = "citable, archived, identifiable release; maintenance risk"
    when = "static"
    tier, effort, proposal = "C", "S–M", "RESPONSIBLE_RSE_PLUGINS.md §2.13"
    hooks = ("project", "@external_tool")
    tools = ("swh.model", "truckfactor", "OpenSSF Scorecard")
