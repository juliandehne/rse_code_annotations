"""Analyzers: the pluggable checks an :class:`~rse_annotations.audit.Audit` runs.

::

    Analyzer (ABC, the plugin contract)
    ├── AnnotationAnalyzer   per annotated function (imports the target)
    │   ├── MathAnalyzer         @functional  -> inferred formula
    │   ├── IOAnalyzer           @data_input / @data_output round trip
    │   └── ConventionAnalyzer   placement + docstring conventions
    ├── StaticAnalyzer       over the AST scan (never imports the target)
    │   ├── CoverageAnalyzer     annotation coverage + candidates
    │   └── HazardAnalyzer       reproducibility hazards
    └── ResponsibleRSEStub   15 course stubs (see .responsible)
"""

from .annotated import ConventionAnalyzer, IOAnalyzer, MathAnalyzer
from .base import PHASES, AnnotationAnalyzer, Analyzer, StaticAnalyzer
from .plugins import BUILTIN_ANALYZERS, ENTRY_POINT_GROUP, AnalyzerCatalog, default_catalog
from .responsible import RESPONSIBLE_ANALYZERS, ResponsibleRSEStub
from .static import CoverageAnalyzer, HazardAnalyzer

__all__ = [
    "PHASES", "Analyzer", "AnnotationAnalyzer", "StaticAnalyzer",
    "MathAnalyzer", "IOAnalyzer", "ConventionAnalyzer", "CoverageAnalyzer", "HazardAnalyzer",
    "AnalyzerCatalog", "default_catalog", "BUILTIN_ANALYZERS", "ENTRY_POINT_GROUP",
    "RESPONSIBLE_ANALYZERS", "ResponsibleRSEStub",
]
