"""Hazard plugin ``security`` -- a stub for students to implement.

Responsible RSE, question 3: *is it safe -- for the people in the data and around the code?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class ResearchSecurity(HazardStub):
    """TODO (Tier A, S): the research-specific slice of security.

    Detect ``pickle.load`` / ``joblib.load`` / ``torch.load(weights_only=False)`` /
    ``yaml.load`` without SafeLoader / ``np.load(allow_pickle=True)`` on ``@data_input``
    paths; ``subprocess(..., shell=True)`` or concatenated argv in external-tool code;
    ``eval`` / ``exec`` on anything reachable from a model-call return value;
    ``verify=False`` on downloads. Filter Bandit (B301/B506/B602/B307/B501) to decorated
    or hazardous code so output stays short. Known-vulnerable dependencies via
    osv-scanner with a pre-fetched offline DB (otherwise a ``ci`` check).
    Difficulty: 2/5 (~2 h/week) -- Bandit and osv-scanner do the detection; the work is
      filtering to decorated/hazardous code and a few own AST patterns.
    EVERSE: indicators ``static_analysis_common_vulnerabilities``,
      ``no_critical_vulnerability``, ``no_leaked_credentials`` (security); RSQKit
      https://everse.software/RSQKit/research_software_security (recommends Bandit,
      gitleaks, OpenSSF Scorecard); resqui's Gitleaks / OpenSSFScorecard plugins.
    """

    name = "security"
    description = "unsafe deserialisation, shell injection, eval of model output"
    question = "is it safe -- for the people in the data and around the code?"
    tier, effort, proposal = "A", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.5"
    difficulty = 2
    hooks = ("@data_input", "external_tool", "model_call")
    tools = ("bandit", "osv-scanner")
