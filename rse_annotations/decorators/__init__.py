"""The role decorators, their registry, and discovery of decorated functions.

This is what *producers* of research code use: they mark what a function is
(``@functional`` maths, ``@mapping``, ``@data_input``, ``@data_output``) so hazard
plugins know where to look. Discovery imports the target to collect the marks.
"""

from .markers import CONCERN_HELP, REVIEW_CONCERNS, HazardDecorator, decorator_of, data_input, data_output, functional, mapping
from .discovery import discover, discover_many, discover_path
from .registry import REGISTRY, DecoratorInfo, Registry

__all__ = ["functional", "mapping", "data_input", "data_output", "decorator_of",
           "HazardDecorator", "REVIEW_CONCERNS", "CONCERN_HELP", "REGISTRY", "Registry", "DecoratorInfo",
           "discover", "discover_many", "discover_path"]
