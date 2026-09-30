"""Hazard plugin ``purpose_retention`` -- a stub for students to implement.

Responsible RSE, question 3: *is it safe -- for the people in the data and around the code?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class PurposeRetention(HazardStub):
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
    question = "is it safe -- for the people in the data and around the code?"
    tier, effort, proposal = "B", "S–M", "RESPONSIBLE_RSE_PLUGINS.md §2.10"
    difficulty = 3
    hooks = ("@data_input", "@data_output", "personal_data")
