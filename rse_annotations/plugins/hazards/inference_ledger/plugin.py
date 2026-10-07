"""Hazard plugin ``inference_ledger`` -- a stub for students to implement.

Responsible RSE, question 2: *is the work fair to the evidence and honest about it?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from ....core.plugin import Phase
from .._stub import HazardStub


class InferenceLedger(HazardStub):
    """TODO (Tier B, M): the garden of forking paths, measured at runtime.

    During a run, wrap ``scipy.stats`` / ``statsmodels`` / ``pingouin`` test functions
    (only when enabled) and record every test: statistic, df, p, calling function.
    Findings: k tests on one outcome without a multiple-comparison correction; p without
    effect size and CI in the same output; tests run vs. tests reported;
    statcheck-style recomputation of p from statistic and df. Static extra: optional
    stopping (test inside a loop that breaks on ``p < alpha``).
    Tools: statsmodels ``multipletests``, scipy.
    Difficulty: 5/5 (~5 h/week) -- runtime instrumentation of three statistics libraries,
      matching tests to reported outputs, and statcheck-style recomputation --
      research-level.
    EVERSE: indicator ``functional_correctness`` only; no EVERSE indicator covers
      inferential practice (multiple testing, forking paths).
    """

    name = "inference_ledger"
    description = "all hypothesis tests actually run vs. those corrected and reported"
    question = "is the work fair to the evidence and honest about it?"
    when = Phase.RUNTIME
    tier, effort, proposal = "B", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.8"
    difficulty = 5
    hooks = ("statistical",)
    tools = ("statsmodels", "scipy")
