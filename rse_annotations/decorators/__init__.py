"""The concerns: one sub-package per decorator, found by :mod:`.registry`.

A new concern is a new folder ``decorators/<name>/`` with one file ``<Name>.py`` (the class
name, as in Java) whose class ``<Name>`` subclasses :class:`Concern`, sets ``assertion``,
and implements ``detect``. The registry creates the instance ``<Name>("<name>")``.
Nothing else needs registering.
"""
from ._base import Concern, FunctionView
from .registry import load, load_one, names

__all__ = ["Concern", "FunctionView", "load", "load_one", "names"]
