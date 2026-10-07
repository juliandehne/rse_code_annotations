"""Hazard plugin ``llm_evaluation`` -- a stub for students to implement.

Responsible RSE, question 2: *is the work fair to the evidence and honest about it?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class LLMEvaluation(HazardStub):
    """TODO (Tier B, M): was the LLM step evaluated, and with a fitting metric?

    This is about an LLM as *part of the computation* of the research software (it
    classifies, extracts, ranks, scores or generates on the way to a result) -- not about
    LLM-generated source code, which ``human_code_inspection`` covers, and not about
    whether the use can be reported, which ``llm_disclosure`` covers.

    For every model-call site, establish the problem type of the step (regression,
    classification, recommendation, generation; declared on the decorator or asked in an
    inspection) and look for the evaluation of its output. Findings: the output reaches a
    result without any evaluation metric; a metric from the wrong family for the problem
    type; ``accuracy`` alone on a classification step (blind to class imbalance); only
    lexical overlap (BLEU, ROUGE) for a generation step, with no execution-based or
    human check; a metric computed without a human-labelled reference
    (no ``human_input`` on the path); a metric computed but never written to an output.
    Start from the metric map in the proposal: the metrics reported per problem type in
    the LLM4SE literature (Hou et al. 2024). It shows what is customary in software
    engineering, not what is correct for every discipline -- make the map configurable.
    Tools: detect metric calls by import (``sklearn.metrics``, ``evaluate``,
      ``sacrebleu``, ``rouge_score``, ``nltk.translate``).
    Implement: ``analyze(target)`` over ``target.static_scan()`` (reuse the ``model_call``
      hazard records and follow the output to a metric call); ``inspect`` to ask for the
      problem type where it cannot be inferred.
    Difficulty: 3/5 (~3 h/week) -- the metric map is given; the work is following a
      model-call output to a metric call and deciding the problem type.
    EVERSE: indicator ``functional_correctness`` only; no EVERSE indicator covers the
      evaluation of an LLM inside the research pipeline.
    """

    name = "llm_evaluation"
    description = "LLM steps used without an evaluation, or with an unfitting metric"
    question = "is the work fair to the evidence and honest about it?"
    tier, effort, proposal = "B", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.16"
    difficulty = 3
    hooks = ("model_call", "human_input")
    tools = ("scikit-learn", "evaluate", "sacrebleu")
