"""The concerns: one sub-package per decorator, found automatically by :mod:`.registry`.

A new concern is a new folder ``decorators/<name>/`` with one file ``<Name>.py`` (the class
name, as in Java) whose class ``<Name>`` subclasses :class:`Concern`, sets ``assertion``,
implements ``detect`` and defines ``CONCERN = <Name>("<name>")``.
Nothing else needs registering.
"""
from ._base import Concern, FunctionView
from .registry import CONCERNS

globals().update(CONCERNS)  # so that ``from rse_annotations import calculations`` works
__all__ = ["CONCERNS", "Concern", "FunctionView", *CONCERNS]
