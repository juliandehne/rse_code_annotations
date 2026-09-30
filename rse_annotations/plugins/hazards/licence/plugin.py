"""Hazard plugin ``licence`` -- a stub for students to implement.

Responsible RSE, question 1: *may the code and its data be reused -- and found again?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class LicenceCompliance(HazardStub):
    """TODO (Tier A, S–M): is the project's licence consistent with what it uses?

    Detect:
      * files without ``SPDX-License-Identifier`` / copyright header (REUSE spec);
      * missing or non-SPDX project licence (FAIR4RS R1.1);
      * outbound licence incompatible with (a) declared dependencies, (b) vendored /
        copied code, (c) bundled ``@external_tool`` binaries.
    Example finding: ``fail pyproject: MIT outbound, depends on GPL-3.0-only 'foo'``.
    Tools: ``reuse lint`` (call as subprocess, GPL), ``license-expression`` to parse SPDX
    expressions, optionally ``scancode-toolkit``; a small compatibility table.
    Implement: ``analyze(target)`` (works on the project tree, not on functions).
    Difficulty: 3/5 (~3 h/week) -- REUSE and SPDX parsing are off the shelf, but resolving
      dependency licences and a defensible compatibility table (OSADL matrix, CC-BY-4.0)
      take design and many test fixtures.
    EVERSE: indicators ``software_has_license``, ``software_has_license_for_file_types``
      (FAIRness); RSQKit https://everse.software/RSQKit/licensing_software ; resqui's
      HowFairIs / RSFC plugins only check presence.
    """

    name = "licence"
    description = "licence presence and compatibility with dependencies / vendored code"
    question = "may the code and its data be reused -- and found again?"
    tier, effort, proposal = "A", "S–M", "RESPONSIBLE_RSE_PLUGINS.md §2.1"
    difficulty = 3
    hooks = ("project", "@external_tool")
    tools = ("reuse", "license-expression", "scancode-toolkit")
