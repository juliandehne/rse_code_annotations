"""rse_code_annotations — role annotations for generated code, with a checking runner.

Public API::

    from rse_annotations import (
        functional, mapping, data_input, data_output,   # the four annotations
        Runner, Report,                                  # the runner
    )
"""

from __future__ import annotations

from .annotations import annotation_of, data_input, data_output, functional, mapping
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
]

__version__ = "0.1.0"
