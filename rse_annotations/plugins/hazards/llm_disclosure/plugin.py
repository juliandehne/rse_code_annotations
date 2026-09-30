"""Hazard plugin ``llm_disclosure`` -- a stub for students to implement.

Responsible RSE, question 2: *is the work fair to the evidence and honest about it?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class LLMDisclosure(HazardStub):
    """TODO (Tier A, S): can the use of an LLM be disclosed and reproduced?

    In model-call sites detect: moving model aliases instead of dated snapshots;
    ``temperature`` / ``top_p`` / ``seed`` / ``max_tokens`` left implicit; prompts built
    from inline f-strings rather than a versioned prompt file; no open-weight baseline;
    no validation against human labels; no "LLM use" statement in README / paper.
    Output: a pre-filled disclosure paragraph (model, version, parameters, prompt hashes,
    role in the pipeline) -- no LLM involved.
    Grounding: llm-guidelines.org (Wagner et al.), TRIPOD-LLM.
    Implement: ``analyze(target)`` over ``target.static_scan()`` (reuse the ``model_call`` hazard records).
    Difficulty: 2/5 (~2 h/week) -- static checks on existing ``model_call`` records plus a
      text template; no runtime part.
    EVERSE: no indicator for LLMs *inside* the research pipeline; RSQKit
      https://everse.software/RSQKit/ai covers gen-AI use while *developing* software
      (intensity levels 0-10) -- cite it as adjacent.
    """

    name = "llm_disclosure"
    description = "LLM usage that cannot be disclosed or reproduced as written"
    question = "is the work fair to the evidence and honest about it?"
    tier, effort, proposal = "A", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.4"
    difficulty = 2
    hooks = ("model_call",)
