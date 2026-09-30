"""Hazard plugin ``dual_use`` -- a stub for students to implement.

Responsible RSE, question 3: *is it safe -- for the people in the data and around the code?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class DualUseScreening(HazardStub):
    """TODO (Tier C, S): prompt a *human* dual-use screen -- not a classifier.

    An import / keyword map flags areas of EU Reg. 2021/821 Annex I (cryptography,
    intrusion software, surveillance) and AI-Act-sensitive uses (biometric identification,
    emotion recognition, social scoring), plus biosecurity (pathogen / protein design).
    The finding asks for a verdict in ``inspection.yaml``: "not listed", "basic scientific
    research", "public domain", or "needs export-control review" (hook into
    :class:`~rse_annotations.review.Reviewer`).
    Difficulty: 2/5 (~2 h/week) -- the code is a keyword/import map plus a reviewer
      verdict; building a defensible map from Annex I and the AI Act is the real work.
    EVERSE: dimension ``safety`` (ISO 25010 sub-characteristics *risk identification*,
      *hazard warning*); no indicator.
    """

    name = "dual_use"
    description = "asks for a human dual-use / AI-Act screen when code touches listed areas"
    question = "is it safe -- for the people in the data and around the code?"
    tier, effort, proposal = "C", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.15"
    difficulty = 2
    hooks = ("project", "model_call", "@data_input")
