"""Hazard plugin ``footprint`` -- a stub for students to implement.

Responsible RSE, question 4: *is it inclusive and sustainable?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class ComputeFootprint(HazardStub):
    """TODO (Tier B, S): a computational-footprint disclosure, including LLM API calls.

    Estimate energy / GWP per model call from model, token counts and latency with
    EcoLogits (offline: 0.11.2 reads bundled model / electricity-mix JSON, no HTTP); add a
    Green-Algorithms-style statement (runtime x cores x TDP x PUE x grid intensity,
    embodied share) with explicit uncertainty.
    Output: a short "computational footprint" paragraph for the paper.
    Difficulty: 2/5 (~2 h/week) -- EcoLogits (offline, bundled model data) does the
      estimate; the work is hooking model calls and writing the disclosure text.
    EVERSE: RSQKit https://everse.software/RSQKit/improving_environmental_sustainability
      (Green Algorithms, CodeCarbon, carbontracker); dimension ``performance_efficiency``;
      no indicator.
    """

    name = "footprint"
    description = "CO2e estimate and disclosure, incl. remote LLM calls"
    question = "is it inclusive and sustainable?"
    when = "runtime"
    tier, effort, proposal = "B", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.12"
    difficulty = 2
    hooks = ("model_call", "run")
    tools = ("ecologits",)
