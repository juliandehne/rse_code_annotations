"""Hazard plugins: one folder per hazard idea, all on the same level.

* :mod:`.human_code_inspection` -- *has a human inspected the (generated) code that
  carries the claim?* The worked example: it implements every mode.
* The Responsible-RSE hazards (``ideas/RESPONSIBLE_RSE_PLUGINS.md``), grouped by the
  question they answer. They are stubs for students: registered, listed, and reported
  as *skipped* until implemented. See :mod:`._stub` for how to implement one.
"""

from __future__ import annotations

from typing import Tuple, Type

from ._stub import NOT_IMPLEMENTED, HazardStub
from .archival import ArchivalSustainability
from .constants import UnjustifiedConstant
from .data_terms import DataTerms
from .dual_use import DualUseScreening
from .fairness import Fairness
from .figure_accessibility import FigureAccessibility
from .footprint import ComputeFootprint
from .human_code_inspection import HumanCodeInspection
from .inclusive_language import InclusiveLanguage
from .inference_ledger import InferenceLedger
from .leakage import DataLeakage
from .licence import LicenceCompliance
from .llm_disclosure import LLMDisclosure
from .llm_evaluation import LLMEvaluation
from .purpose_retention import PurposeRetention
from .security import ResearchSecurity
from .silent_failures import SilentFailure

#: The Responsible-RSE stubs in proposal order (§2.1 ... §2.16).
RESPONSIBLE_HAZARDS: Tuple[Type[HazardStub], ...] = (
    LicenceCompliance, SilentFailure, UnjustifiedConstant,
    LLMDisclosure, ResearchSecurity, DataTerms,
    DataLeakage, InferenceLedger, Fairness,
    PurposeRetention, FigureAccessibility, ComputeFootprint,
    ArchivalSustainability, InclusiveLanguage, DualUseScreening,
    LLMEvaluation,
)

#: Every hazard plugin shipped with the package: the implemented one first.
HAZARD_PLUGINS = (HumanCodeInspection,) + RESPONSIBLE_HAZARDS

__all__ = ["HAZARD_PLUGINS", "RESPONSIBLE_HAZARDS", "HazardStub", "NOT_IMPLEMENTED",
           "HumanCodeInspection"] + [c.__name__ for c in RESPONSIBLE_HAZARDS]
