"""Responsible RSE, question 4: *is it inclusive and sustainable?*"""

from __future__ import annotations

from ._stub import ResponsibleRSEStub


class FairnessAnalyzer(ResponsibleRSEStub):
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
    when = "test"
    tier, effort, proposal = "B", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.9"
    difficulty = 3
    hooks = ("statistical", "model_call", "@data_output")
    tools = ("fairlearn", "aequitas")


class FigureAccessibilityAnalyzer(ResponsibleRSEStub):
    """TODO (Tier B, M): figures readable by colour-vision-deficient readers.

    Static: ``cmap="jet" | "rainbow" | "hsv"``, red/green pairs, legends distinguished by
    colour only. Runtime: hook ``Figure.savefig`` in ``@data_output`` functions, simulate
    deutan / protan / tritan with daltonlens, compare series colours with colorspacious
    (CAM02-UCS); flag close pairs, fonts under ~8 pt, figures without alt text.
    Difficulty: 3/5 (~3 h/week) -- a ``savefig`` hook, colour extraction from matplotlib
      artists and CVD simulation; each needs visual test fixtures.
    EVERSE: dimension ``interaction_capability`` (ISO 25010 sub-characteristic
      *inclusivity*); no indicator.
    """

    name = "figure_accessibility"
    description = "colour-blind-safe, labelled, alt-texted figures"
    tier, effort, proposal = "B", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.11"
    difficulty = 3
    hooks = ("@data_output",)
    tools = ("colorspacious", "daltonlens")


class ComputeFootprintAnalyzer(ResponsibleRSEStub):
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
    when = "runtime"
    tier, effort, proposal = "B", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.12"
    difficulty = 2
    hooks = ("model_call", "run")
    tools = ("ecologits",)


class InclusiveLanguageAnalyzer(ResponsibleRSEStub):
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
    tier, effort, proposal = "C", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.14"
    difficulty = 1
    hooks = ("human_input", "docs")
