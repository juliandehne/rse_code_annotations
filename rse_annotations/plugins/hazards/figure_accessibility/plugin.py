"""Hazard plugin ``figure_accessibility`` -- a stub for students to implement.

Responsible RSE, question 4: *is it inclusive and sustainable?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class FigureAccessibility(HazardStub):
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
    question = "is it inclusive and sustainable?"
    tier, effort, proposal = "B", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.11"
    difficulty = 3
    hooks = ("@data_output",)
    tools = ("colorspacious", "daltonlens")
