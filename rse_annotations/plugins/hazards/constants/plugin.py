"""Hazard plugin ``constants`` -- a stub for students to implement.

Responsible RSE, question 2: *is the work fair to the evidence and honest about it?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class UnjustifiedConstant(HazardStub):
    """TODO (Tier A, S): researcher degrees of freedom hidden in magic numbers.

    Detect numeric literals in comparisons, slicing, ``quantile``, ``head(n)``,
    ``sample(frac=)`` and filter masks inside unit-of-analysis, statistical and
    ``@mapping`` code that are not a configurable parameter and carry no justification
    (inline comment / ``rationale=``). Whitelist 0, 1, -1, 2 and array axes. List each
    constant as a candidate configuration value.
    Tools: ruff PLR2004 as a baseline, own AST for the other positions.
    Implement: ``analyze(target)`` over ``target.static_scan()``.
    Difficulty: 2/5 (~2 h/week) -- AST plus comment lookup via ``tokenize``; the hard part
      is a whitelist that keeps false positives low.
    EVERSE: no matching indicator; closest ``functional_correctness``
      (functional_suitability) and RSQKit
      https://everse.software/RSQKit/writing_readable_code .
    """

    name = "constants"
    description = "unjustified thresholds and cut-offs in decision logic"
    question = "is the work fair to the evidence and honest about it?"
    tier, effort, proposal = "A", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.3"
    difficulty = 2
    hooks = ("@mapping", "unit_of_analysis", "statistical")
    tools = ("ruff",)
