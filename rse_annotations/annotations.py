"""The four code annotations.

Each is a decorator that attaches :class:`~rse_annotations.registry.AnnotationInfo`
to the decorated function and registers it in the global
:data:`~rse_annotations.registry.REGISTRY`. The decorators are behaviour-preserving:
the wrapper simply forwards ``*args, **kwargs`` to the original function, so it is
safe to leave the annotations in production code.

Usage::

    from rse_annotations import functional, mapping, data_input, data_output

    @functional
    def rescale(x, lo, hi):
        "Map x from [0,1] to [lo, hi]."
        return lo + x * (hi - lo)

    @data_input(fields={"path": "CSV file to read", "rows": "parsed records"})
    def load_csv(path):
        "Read rows from a CSV file. :param path: source file. :returns rows:"
        ...

Both bare (``@functional``) and called (``@data_input(fields=...)``) forms are
supported for every annotation.
"""

from __future__ import annotations

import functools
from typing import Callable, Dict, Optional

from .registry import REGISTRY, build_info


def _make_decorator(kind: str):
    """Return a decorator for ``kind`` supporting both @deco and @deco(...) forms."""

    def decorator(func: Optional[Callable] = None, *, fields: Optional[Dict[str, str]] = None):
        def wrap(fn: Callable) -> Callable:
            info = build_info(kind, fn, fields)

            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                return fn(*args, **kwargs)

            # Expose metadata on both the wrapper and the raw function.
            wrapper.__rse_annotation__ = info
            fn.__rse_annotation__ = info
            REGISTRY.add(info)
            return wrapper

        # Bare form: @functional  -> func is the function.
        if callable(func) and fields is None:
            return wrap(func)
        # Called form: @functional(fields=...) -> return the real decorator.
        return wrap

    decorator.__name__ = kind
    decorator.__doc__ = f"Annotate a function as `{kind}` code."
    return decorator


#: Marks a pure mathematical function (deterministic, no I/O, no globals).
functional = _make_decorator("functional")

#: Marks code that maps/transforms one data format or object into another.
mapping = _make_decorator("mapping")

#: Marks a boundary where data enters the system (reads a source/file).
data_input = _make_decorator("data_input")

#: Marks a boundary where data leaves the system (writes a sink/file).
data_output = _make_decorator("data_output")


def annotation_of(func: Callable):
    """Return the :class:`AnnotationInfo` attached to ``func`` (or ``None``)."""
    return getattr(func, "__rse_annotation__", None)
