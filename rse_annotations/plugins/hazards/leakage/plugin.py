"""Hazard plugin ``leakage`` -- a stub for students to implement.

Responsible RSE, question 2: *is the work fair to the evidence and honest about it?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class DataLeakage(HazardStub):
    """TODO (Tier B, M): train/test contamination (Yang et al., ASE 2022).

    Static: preprocessing ``fit`` / ``fit_transform`` before ``train_test_split``; test
    set evaluated repeatedly during model selection; random split on time-stamped or
    grouped data (same subject in both splits). Test mode (``when="test"`` part): hash
    the rows of the actual splits and report overlap.
    Tools: implement the preprocessing-before-split pattern in own AST first;
    ``leakage-analysis`` is heavy (Py3.8, Soufflé) -- optional backend only.
    Difficulty: 4/5 (~4 h/week) -- needs intra-procedural dataflow (what was fitted on
      what, before which split) plus a runtime hashing mode; published tools are too heavy
      to reuse.
    EVERSE: indicator ``functional_correctness`` (asks for a quantifiable correctness
      measure -- leakage invalidates it); RSQKit
      https://everse.software/RSQKit/testing_software .
    """

    name = "leakage"
    description = "train/test leakage: preprocessing before split, overlap, reuse"
    question = "is the work fair to the evidence and honest about it?"
    tier, effort, proposal = "B", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.7"
    difficulty = 4
    hooks = ("stochastic", "statistical", "unit_of_analysis")
    tools = ("leakage-analysis (optional)",)
