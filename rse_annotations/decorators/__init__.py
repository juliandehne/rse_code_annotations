"""The role decorators, their registry, and discovery of decorated functions.

This is what *producers* of research code use: they mark what a function is
(``@functional`` maths, ``@mapping``, ``@data_input``, ``@data_output``) so hazard
plugins know where to look. Discovery imports the target to collect the marks.
"""

from . import markers
from .markers import *  # noqa: F401,F403 -- every decorator plus the derived tables (markers.__all__)
from .discovery import discover, discover_many, discover_path
from .registry import REGISTRY, DecoratorInfo, Registry

__all__ = [*markers.__all__, "REGISTRY", "Registry", "DecoratorInfo",
           "discover", "discover_many", "discover_path"]
