"""Concern decorators for generated research code, plus a static analysis and a review runner.

    from rse_annotations import calculations, data_input

    @calculations
    def normalize(x, lo, hi):
        return (x - lo) / (hi - lo)

Importing the package computes nothing. A concern is loaded only when its name is
imported: ``from rse_annotations import calculations`` calls :func:`__getattr__`, which
creates that one instance via the registry.
"""
from .decorators import Concern, FunctionView, load, load_one, names

__all__ = ["Concern", "FunctionView", "load", "load_one", "names"]


def __getattr__(name: str) -> Concern:
    """``from rse_annotations import <concern>`` (PEP 562): load just that concern."""
    if name in names():
        return load_one(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
