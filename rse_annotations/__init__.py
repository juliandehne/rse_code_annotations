"""rse_code_annotations — role annotations for generated code, with a checking runner.

Public API::

    from rse_annotations import (
        functional, mapping, data_input, data_output,   # the four annotations
        Runner, Report,                                  # the runner
    )
"""

from __future__ import annotations

from .annotations import annotation_of, data_input, data_output, functional, mapping
from .registry import REGISTRY, AnnotationInfo, KINDS, Registry
from .runner import Report, Runner, render_json, render_text

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
    "Runner",
    "Report",
    "render_text",
    "render_json",
]

__version__ = "0.1.0"
