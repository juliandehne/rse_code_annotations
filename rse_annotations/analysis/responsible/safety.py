"""Responsible RSE, question 3: *is it safe -- for the people in the data and around the code?*"""

from __future__ import annotations

from ._stub import ResponsibleRSEStub


class ResearchSecurityAnalyzer(ResponsibleRSEStub):
    """TODO (Tier A, S): the research-specific slice of security.

    Detect ``pickle.load`` / ``joblib.load`` / ``torch.load(weights_only=False)`` /
    ``yaml.load`` without SafeLoader / ``np.load(allow_pickle=True)`` on ``@data_input``
    paths; ``subprocess(..., shell=True)`` or concatenated argv in external-tool code;
    ``eval`` / ``exec`` on anything reachable from a model-call return value;
    ``verify=False`` on downloads. Filter Bandit (B301/B506/B602/B307/B501) to annotated
    or hazardous code so output stays short. Known-vulnerable dependencies via
    osv-scanner with a pre-fetched offline DB (otherwise a ``ci`` check).
    Difficulty: 2/5 (~2 h/week) -- Bandit and osv-scanner do the detection; the work is
      filtering to annotated/hazardous code and a few own AST patterns.
    EVERSE: indicators ``static_analysis_common_vulnerabilities``,
      ``no_critical_vulnerability``, ``no_leaked_credentials`` (security); RSQKit
      https://everse.software/RSQKit/research_software_security (recommends Bandit,
      gitleaks, OpenSSF Scorecard); resqui's Gitleaks / OpenSSFScorecard plugins.
    """

    name = "security"
    description = "unsafe deserialisation, shell injection, eval of model output"
    tier, effort, proposal = "A", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.5"
    difficulty = 2
    hooks = ("@data_input", "external_tool", "model_call")
    tools = ("bandit", "osv-scanner")


class PurposeRetentionAnalyzer(ResponsibleRSEStub):
    """TODO (Tier B, S–M): GDPR purpose limitation and storage limitation.

    Build on a ``personal_data`` hazard (do not re-detect PII). Detect personal-data
    ``@data_input`` without ``purpose=``, ``legal_basis=`` (Art. 6 / 9) and
    ``retention=``; flows into a ``@data_output`` with a different purpose; personal data
    persisted without pseudonymisation or a deletion step; special-category fields without
    an Art. 9 basis. Output: a draft Art. 30 record of processing for the DPO / ethics board.
    Difficulty: 3/5 (~3 h/week) -- depends on a ``personal_data`` hazard that may have to
      be built first, plus reading GDPR Art. 5/6/9/30 carefully for the draft record.
    EVERSE: no indicator (ISO 25010 ``safety`` / ``security`` dimensions only loosely); a
      gap in EVERSE worth citing as such.
    """

    name = "purpose_retention"
    description = "personal data without purpose, legal basis or retention"
    tier, effort, proposal = "B", "S–M", "RESPONSIBLE_RSE_PLUGINS.md §2.10"
    difficulty = 3
    hooks = ("@data_input", "@data_output", "personal_data")


class DualUseScreeningAnalyzer(ResponsibleRSEStub):
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
    tier, effort, proposal = "C", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.15"
    difficulty = 2
    hooks = ("project", "model_call", "@data_input")
