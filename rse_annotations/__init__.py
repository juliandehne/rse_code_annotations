"""rse_code_annotations — role annotations for generated code, with a checking runner.

Public API::

    from rse_annotations import (
        functional, mapping, data_input, data_output,   # the four annotations
        Runner, Report,                                  # the runner
    )

Object model (the classes the CLI is built on)::

    from rse_annotations import (
        TargetProject,                      # what is analyzed (path or git URL)
        Audit, AuditReport,                 # run analyzers over a target
        Analyzer, AnalyzerCatalog,          # the plugin contract + registry
        Reviewer, VerdictStore,             # human verdicts (inspection.yaml)
        TextRenderer, MarkdownRenderer, JsonRenderer,
        TestGenerator, DifferentialVerifier,
    )
"""

from __future__ import annotations

from .analysis import (BUILTIN_ANALYZERS, ENTRY_POINT_GROUP, PHASES,
                       RESPONSIBLE_ANALYZERS, AnalyzerCatalog, Analyzer,
                       AnnotationAnalyzer, ConventionAnalyzer, CoverageAnalyzer,
                       HazardAnalyzer, IOAnalyzer, MathAnalyzer, ResponsibleRSEStub,
                       StaticAnalyzer, default_catalog)
from .audit import Audit, AuditReport
from .findings import SEVERITIES, AnalysisResult, Finding
from .rendering import JsonRenderer, MarkdownRenderer, Renderer, TextRenderer
from .review import Reviewer, VerdictStore
from .target import TargetProject
from .testing import DifferentialVerifier, TestGenerator
from .annotations import annotation_of, data_input, data_output, functional, mapping
from .coverage import (CRITICAL_HAZARDS, HAZARD_HELP, HAZARD_PARENT, HAZARDS,
                       CoverageReport, FunctionRecord, Hazard,
                       render_coverage_markdown, render_coverage_text, scan_path)
from .registry import REGISTRY, AnnotationInfo, KINDS, KIND_HELP, Registry
from .runner import Report, Runner, render_json, render_text
from .snippets import Snippet, extract_snippet
from .stubs import StubFile, generate_stub_files
from .verify import DiffResult, differential_check

__all__ = [
    "functional",
    "mapping",
    "data_input",
    "data_output",
    "annotation_of",
    "REGISTRY",
    "Registry",
    "AnnotationInfo",
    "KINDS",
    "KIND_HELP",
    "Runner",
    "Report",
    "render_text",
    "render_json",
    "Snippet",
    "extract_snippet",
    "StubFile",
    "generate_stub_files",
    "differential_check",
    "DiffResult",
    "scan_path",
    "CoverageReport",
    "FunctionRecord",
    "render_coverage_text",
    "render_coverage_markdown",
    "Hazard",
    "HAZARDS",
    "HAZARD_PARENT",
    "HAZARD_HELP",
    "CRITICAL_HAZARDS",
    # object model
    "TargetProject",
    "Finding",
    "AnalysisResult",
    "SEVERITIES",
    "Analyzer",
    "AnnotationAnalyzer",
    "StaticAnalyzer",
    "PHASES",
    "MathAnalyzer",
    "IOAnalyzer",
    "ConventionAnalyzer",
    "CoverageAnalyzer",
    "HazardAnalyzer",
    "ResponsibleRSEStub",
    "RESPONSIBLE_ANALYZERS",
    "BUILTIN_ANALYZERS",
    "AnalyzerCatalog",
    "default_catalog",
    "ENTRY_POINT_GROUP",
    "Audit",
    "AuditReport",
    "Reviewer",
    "VerdictStore",
    "Renderer",
    "TextRenderer",
    "MarkdownRenderer",
    "JsonRenderer",
    "TestGenerator",
    "DifferentialVerifier",
]

__version__ = "0.1.0"
