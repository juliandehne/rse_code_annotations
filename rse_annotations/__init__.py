"""rse_code_annotations -- producers mark their research code, hazard plugins check it.

Layout::

    annotations/  the four marks (@functional, @mapping, @data_input, @data_output)
    scan/         static AST scan: coverage, candidates, hazards (never imports code)
    inspection/   the human review loop, verdicts, formula inference, snippets
    testing/      test-scaffold generation and differential verification
    reporting/    every renderer (text, markdown, json, coverage report)
    core/         TargetProject, Plugin contract, PluginCatalog, Audit, Finding
    plugins/      everything that checks something, e.g.
                  plugins/hazards/human_code_inspection  (the worked example)
                  plugins/hazards/<responsible-RSE hazard> (stubs)
    cli.py        general entry point: pick inspection / analysis / test generation

Public API::

    from rse_annotations import (
        functional, mapping, data_input, data_output,   # the four annotations
        TargetProject, Audit,                            # run plugins over a project
        Plugin, PluginCatalog, default_catalog,          # the plugin contract + registry
        HumanCodeInspection,                             # the worked-example plugin
    )
"""

from __future__ import annotations

from .annotations import (KIND_HELP, KINDS, REGISTRY, AnnotationInfo, Registry, annotation_of,
                          data_input, data_output, functional, mapping)
from .core import (ENTRY_POINT_GROUP, MODE_LABELS, MODES, PHASES, SEVERITIES, AnalysisResult,
                   Audit, AuditReport, Finding, Plugin, PluginCatalog, TargetProject,
                   default_catalog)
from .inspection import Reviewer, Snippet, VerdictStore, extract_snippet
from .legacy import Report, Runner, render_json, render_text
from .plugins import BUILTIN_PLUGINS, HAZARD_PLUGINS
from .plugins.hazards import RESPONSIBLE_HAZARDS, HazardStub
from .plugins.hazards.human_code_inspection import FACETS, HumanCodeInspection
from .reporting import (JsonRenderer, MarkdownRenderer, Renderer, TextRenderer,
                        render_coverage_markdown, render_coverage_text)
from .scan import (CRITICAL_HAZARDS, HAZARD_HELP, HAZARD_PARENT, HAZARDS, CoverageReport,
                   FunctionRecord, Hazard, scan_path)
from .testing import (DiffResult, DifferentialVerifier, StubFile, TestGenerator,
                      differential_check, generate_stub_files)

__all__ = [
    # annotations
    "functional", "mapping", "data_input", "data_output", "annotation_of",
    "REGISTRY", "Registry", "AnnotationInfo", "KINDS", "KIND_HELP",
    # core
    "TargetProject", "Plugin", "PHASES", "MODES", "MODE_LABELS",
    "Finding", "AnalysisResult", "SEVERITIES",
    "PluginCatalog", "default_catalog", "ENTRY_POINT_GROUP", "Audit", "AuditReport",
    # plugins
    "BUILTIN_PLUGINS", "HAZARD_PLUGINS", "RESPONSIBLE_HAZARDS", "HazardStub",
    "HumanCodeInspection", "FACETS",
    # shared machinery
    "scan_path", "CoverageReport", "FunctionRecord", "Hazard", "HAZARDS", "HAZARD_PARENT",
    "HAZARD_HELP", "CRITICAL_HAZARDS",
    "Reviewer", "VerdictStore", "Snippet", "extract_snippet",
    "TestGenerator", "DifferentialVerifier", "StubFile", "generate_stub_files",
    "DiffResult", "differential_check",
    "Renderer", "TextRenderer", "MarkdownRenderer", "JsonRenderer",
    "render_coverage_text", "render_coverage_markdown",
    # deprecated per-function view
    "Runner", "Report", "render_text", "render_json",
]

__version__ = "0.2.0"
