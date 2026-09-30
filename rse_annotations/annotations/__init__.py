"""The four role annotations, their registry, and discovery of annotated functions.

This is what *producers* of research code use: they mark what a function is
(``@functional`` maths, ``@mapping``, ``@data_input``, ``@data_output``) so hazard
plugins know where to look. Discovery imports the target to collect the marks.
"""

from .decorators import annotation_of, data_input, data_output, functional, mapping
from .discovery import discover, discover_many, discover_path
from .registry import KIND_HELP, KINDS, REGISTRY, AnnotationInfo, Registry

__all__ = ["functional", "mapping", "data_input", "data_output", "annotation_of",
           "KINDS", "KIND_HELP", "REGISTRY", "Registry", "AnnotationInfo",
           "discover", "discover_many", "discover_path"]
