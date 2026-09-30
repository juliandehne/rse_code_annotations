"""Hazard plugin ``inclusive_language`` -- a stub for students to implement.

Responsible RSE, question 4: *is it inclusive and sustainable?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class InclusiveLanguage(HazardStub):
    """TODO (Tier C, S): non-inclusive terms and exclusionary categories.

    Scan identifiers, comments, docstrings and docs with a woke/alex-style rules file
    (``master/slave``, ``whitelist``, ...; pure Python, no Go/Node dependency). Research
    extra: codebooks read by human-input code (binary-only gender without "other / not
    stated", deficit-framed labels). High false-positive risk: ``info`` severity only.
    Difficulty: 1/5 (~1 h/week) -- a rules file and a tokenizer scan at ``info`` severity;
      the codebook part is a small extension.
    EVERSE: dimensions ``interaction_capability`` (*inclusivity*) and ``community``;
      RSQKit https://everse.software/RSQKit/code_of_conduct ; no indicator.
    """

    name = "inclusive_language"
    description = "non-inclusive terms in code/docs; binary-only categories in codebooks"
    question = "is it inclusive and sustainable?"
    tier, effort, proposal = "C", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.14"
    difficulty = 1
    hooks = ("human_input", "docs")
