"""Responsible-RSE analyzers -- stubs for students to implement.

Fifteen checks proposed in ``RESPONSIBLE_RSE_PLUGINS.md``, grouped by the question they
answer. They are registered in the default catalog so they show up in
``--list-analyzers`` and are reported as *skipped* until implemented. See
:mod:`._stub` for how to turn a stub into a working analyzer.
"""

from __future__ import annotations

from typing import Tuple, Type

from ._stub import NOT_IMPLEMENTED, ResponsibleRSEStub
from .inclusion import (ComputeFootprintAnalyzer, FairnessAnalyzer,
                        FigureAccessibilityAnalyzer, InclusiveLanguageAnalyzer)
from .integrity import (DataLeakageAnalyzer, InferenceLedgerAnalyzer, LLMDisclosureAnalyzer,
                        SilentFailureAnalyzer, UnjustifiedConstantAnalyzer)
from .reuse import ArchivalSustainabilityAnalyzer, DataTermsAnalyzer, LicenceComplianceAnalyzer
from .safety import DualUseScreeningAnalyzer, PurposeRetentionAnalyzer, ResearchSecurityAnalyzer

#: In proposal order (§2.1 ... §2.15).
RESPONSIBLE_ANALYZERS: Tuple[Type[ResponsibleRSEStub], ...] = (
    LicenceComplianceAnalyzer, SilentFailureAnalyzer, UnjustifiedConstantAnalyzer,
    LLMDisclosureAnalyzer, ResearchSecurityAnalyzer, DataTermsAnalyzer,
    DataLeakageAnalyzer, InferenceLedgerAnalyzer, FairnessAnalyzer,
    PurposeRetentionAnalyzer, FigureAccessibilityAnalyzer, ComputeFootprintAnalyzer,
    ArchivalSustainabilityAnalyzer, InclusiveLanguageAnalyzer, DualUseScreeningAnalyzer,
)

__all__ = ["RESPONSIBLE_ANALYZERS", "ResponsibleRSEStub", "NOT_IMPLEMENTED"] + [
    c.__name__ for c in RESPONSIBLE_ANALYZERS]
