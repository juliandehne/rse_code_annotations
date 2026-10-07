"""rse_code_annotations -- producers mark their research code, hazard plugins check it.

Layout::

    decorators/  the marks (@functional, @mapping, @data_input, @data_output, ...)
    scan/         static AST scan: coverage, candidates, hazards (never imports code)
    inspection/   the human review loop, verdicts, formula inference, snippets
    testing/      test-scaffold generation and differential verification
    reporting/    every renderer (text, markdown, json, coverage report)
    core/         TargetProject, Plugin contract, PluginCatalog, Audit, Finding
    plugins/      everything that checks something, e.g.
                  plugins/hazards/human_code_inspection  (the worked example)
                  plugins/hazards/<responsible-RSE hazard> (stubs)
    cli.py        general entry point: pick inspection / analysis / test generation / external review
    manager.py    what the features share: the Manager (target, plugins, user I/O)
    start_*.py    the program flow of one feature each (inspection, review, analysis,
                  test generation); run one directly, or via cli.py
    textenum.py   the base of every enum (Mode, Phase, Severity, Status, Decision, ...)

Public API::

    from rse_annotations import (
        functional, mapping, data_input, data_output,   # the decorators
        TargetProject, Audit,                            # run plugins over a project
        Plugin, PluginCatalog, default_catalog,          # the plugin contract + registry
        HumanCodeInspection,                             # the worked-example plugin
    )
"""

from __future__ import annotations

from . import decorators
from .decorators import *  # noqa: F401,F403 -- every decorator and its tables (decorators.__all__)
from .core import (ENTRY_POINT_GROUP, MODE_LABELS, MODES, PHASES, SEVERITIES, AnalysisResult,
                   Audit, AuditReport, Finding, Mode, Phase, Plugin, PluginCatalog, Severity,
                   Status, TargetProject, default_catalog)
from .inspection import Decision, ExternalReviewer, ProtocolStore, Reviewer, Snippet, VerdictStore, extract_snippet
from .legacy import Report, Runner, render_json, render_text
from .plugins import BUILTIN_PLUGINS, HAZARD_PLUGINS
from .plugins.hazards import RESPONSIBLE_HAZARDS, HazardStub
from .plugins.hazards.human_code_inspection import FACETS, Facet, HumanCodeInspection
from .reporting import (JsonRenderer, MarkdownRenderer, OutputFormat, Renderer, TextRenderer,
                        render_coverage_markdown, render_coverage_text)
from .scan import (CRITICAL_HAZARDS, HAZARD_HELP, HAZARD_KINDS, HAZARD_PARENT, HAZARDS, CoverageReport,
                   FunctionRecord, Hazard, HazardKind, scan_path)
from .testing import (DiffResult, DifferentialVerifier, StubFile, TestGenerator,
                      differential_check, generate_stub_files)

__all__ = [
    # decorators: whatever rse_annotations.decorators exports
    *decorators.__all__,
    # core
    "TargetProject", "Plugin", "Phase", "PHASES", "Mode", "MODES", "MODE_LABELS",
    "Finding", "AnalysisResult", "Severity", "Status", "SEVERITIES",
    "PluginCatalog", "default_catalog", "ENTRY_POINT_GROUP", "Audit", "AuditReport",
    # plugins
    "BUILTIN_PLUGINS", "HAZARD_PLUGINS", "RESPONSIBLE_HAZARDS", "HazardStub",
    "HumanCodeInspection", "Facet", "FACETS",
    # shared machinery
    "scan_path", "CoverageReport", "FunctionRecord", "Hazard", "HAZARDS", "HAZARD_PARENT",
    "HAZARD_HELP", "CRITICAL_HAZARDS", "HazardKind", "HAZARD_KINDS",
    "Reviewer", "ExternalReviewer", "Decision", "ProtocolStore", "VerdictStore", "Snippet", "extract_snippet",
    "TestGenerator", "DifferentialVerifier", "StubFile", "generate_stub_files",
    "DiffResult", "differential_check",
    "OutputFormat", "Renderer", "TextRenderer", "MarkdownRenderer", "JsonRenderer",
    "render_coverage_text", "render_coverage_markdown",
    # deprecated per-function view
    "Runner", "Report", "render_text", "render_json",
]

__version__ = "0.2.0"
