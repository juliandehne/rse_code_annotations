"""Hazard plugin ``data_terms`` -- a stub for students to implement.

Responsible RSE, question 1: *may the code and its data be reused -- and found again?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class DataTerms(HazardStub):
    """TODO (Tier A, M): are the data used and published under terms that allow it?

    Inbound: every ``@data_input`` / ``@human_input`` declares ``source=``, ``license=``
    and, for data about people, ``consent=`` / ``legal_basis=``. Flag missing terms,
    licences that forbid the use (NC, ND, "research only" re-published), and scraping
    (``requests`` / ``BeautifulSoup`` in a ``@data_input``) without a ToS note.
    Outbound: a published ``@data_output`` needs a datasheet / data statement / Croissant
    file with RAI fields; a saved model needs a model card. Propagate the most
    restrictive input licence to each output along the call graph (like hazards).
    Tools: ``mlcroissant``, ``huggingface_hub.ModelCard``.
    Difficulty: 3/5 (~3 h/week) -- new decorator kwargs, licence propagation over the call
      graph and Croissant / model-card validation; each part is small, together they need
      design.
    EVERSE: no data-licence indicator (a gap on their side); closest are
      ``descriptive_metadata`` and RSQKit https://everse.software/RSQKit/fair_rs /
      https://everse.software/RSQKit/software_metadata .
    """

    name = "data_terms"
    description = "data licences, consent and datasheets / model cards for outputs"
    question = "may the code and its data be reused -- and found again?"
    tier, effort, proposal = "A", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.6"
    difficulty = 3
    hooks = ("@data_input", "@human_input", "@data_output")
    tools = ("mlcroissant", "huggingface_hub")
