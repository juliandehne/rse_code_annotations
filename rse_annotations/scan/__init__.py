"""The static AST scan: every function, its decorator, candidates and hazards.

Never imports or runs the target, so it works on code that does not import cleanly.
Shared by any plugin that needs a syntactic view of the code
(``target.static_scan()`` caches one :class:`CoverageReport` per target).
"""

from .hazards import (CRITICAL_HAZARDS, HAZARD_HELP, HAZARD_KINDS, HAZARD_PARENT, HAZARDS, Hazard,
                      HazardKind)
from .model import CoverageReport, FunctionRecord
from .scanner import scan_path

__all__ = ["scan_path", "CoverageReport", "FunctionRecord", "Hazard", "HazardKind", "HAZARD_KINDS", "HAZARDS",
           "HAZARD_PARENT", "HAZARD_HELP", "CRITICAL_HAZARDS"]
