"""Hazard plugin ``fairness`` -- a stub for students to implement.

Responsible RSE, question 4: *is it inclusive and sustainable?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from ....core.plugin import Phase
from .._stub import HazardStub


class Fairness(HazardStub):
    """TODO (Tier B, M): disaggregated performance across declared sensitive attributes.

    Only when the author declares ``sensitive=[...]``: accuracy, FPR/FNR and selection
    rate per group and the largest gap (``fairlearn.metrics.MetricFrame``); groups too
    small to estimate a rate; for LLM annotation pipelines, agreement with human gold per
    subgroup. Static extra: protected-attribute-like columns used as features without a
    declaration. Report numbers only -- which fairness definition applies is a human
    verdict. Also a ``runtime`` check.
    Difficulty: 3/5 (~3 h/week) -- fairlearn computes the metrics; capturing predictions
      and declared groups at test/runtime needs design.
    EVERSE: none -- note that EVERSE's ``fairness`` dimension means *FAIRness* (FAIR
      principles), not algorithmic fairness; do not conflate them.
    """

    name = "fairness"
    description = "per-group error / selection rates for declared sensitive attributes"
    question = "is it inclusive and sustainable?"
    when = Phase.TEST
    tier, effort, proposal = "B", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.9"
    difficulty = 3
    hooks = ("statistical", "model_call", "@data_output")
    tools = ("fairlearn", "aequitas")
