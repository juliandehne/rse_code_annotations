"""The code decorators.

A decorator is a function that takes a function and returns a function:
``@functional`` above ``def f`` is short for ``f = functional(f)``. Each decorator
here attaches a :class:`~rse_annotations.decorators.registry.DecoratorInfo` to the
function, registers it in the global
:data:`~rse_annotations.decorators.registry.REGISTRY` and returns the function
unchanged, so it is safe to leave the decorators in production code.

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

A new decorator is one function below, marked with ``@_concern``. Nothing else changes:
its name becomes a :class:`HazardDecorator` member, its docstring the help text, and it is
exported from :mod:`rse_annotations` and recognised by the scanner.
"""

from __future__ import annotations

import inspect
from enum import Enum
from typing import Callable, Dict, List, Optional

from .registry import REGISTRY, build_info

_DEFINED: List[Callable] = []


def _concern(decorator: Callable) -> Callable:
    """Register ``decorator`` as a role decorator (in definition order = listing order)."""
    _DEFINED.append(decorator)
    return decorator


def _mark(decorator: Callable, fn: Optional[Callable], fields: Optional[Dict[str, str]]):
    """Record ``fn`` under the concern named like ``decorator`` and return it unchanged.

    ``@data_input`` passes the function directly (``fn`` is set).
    ``@data_input(fields=...)`` passes no function, so return a decorator that
    waits for it.
    """
    if fn is None:
        return lambda f: _mark(decorator, f, fields)
    info = build_info(HazardDecorator(decorator.__name__), fn, fields)
    fn.__rse_decorator__ = info
    REGISTRY.add(info)
    return fn


@_concern
def functional(fn=None, *, fields=None):
    """Marks a pure mathematical function (deterministic, no I/O, no globals).

    Review the math: wrong formula, wrong denominator, numerical error.
    """
    return _mark(functional, fn, fields)


@_concern
def mapping(fn=None, *, fields=None):
    """Marks code that maps/transforms one data format or object into another.

    Review for lost or distorted information: dropped rows, units, encoding.
    """
    return _mark(mapping, fn, fields)


@_concern
def data_input(fn=None, *, fields=None):
    """Marks a boundary where data enters the system (reads a source/file).

    Review for wrong or mis-parsed data: wrong file, delimiter, missing values.
    """
    return _mark(data_input, fn, fields)


@_concern
def data_output(fn=None, *, fields=None):
    """Marks a boundary where data leaves the system (writes a sink/file).

    Review for incomplete or unreproducible results.
    """
    return _mark(data_output, fn, fields)


@_concern
def hardware_dependency(fn=None, *, fields=None):
    """Marks code that needs specific hardware to run or to give the same result (e.g. a GPU).

    Review whether the hardware is stated in the paper/README and whether a CPU fallback
    changes the result (precision, non-deterministic kernels).
    """
    return _mark(hardware_dependency, fn, fields)


def decorator_of(func: Callable):
    """Return the :class:`DecoratorInfo` attached to ``func`` (or ``None``)."""
    return getattr(func, "__rse_decorator__", None)


#: The decorators above, in definition order. Everything below is derived from it.
DECORATORS = tuple(_DEFINED)


class _ConcernEnum(str, Enum):
    def __str__(self) -> str:   # "functional", not "HazardDecorator.FUNCTIONAL" (also in f-strings)
        return self.value


#: The review concerns as an enum, one member per decorator, named like it
#: (``HazardDecorator.FUNCTIONAL == "functional"``). A ``str`` subclass, so it is written
#: to YAML/JSON as plain text.
HazardDecorator = _ConcernEnum(
    "HazardDecorator", [(d.__name__.upper(), d.__name__) for d in DECORATORS], module=__name__)
HazardDecorator.__doc__ = "The review concerns: kinds of code where the scientific result can go wrong."

#: The review concerns: kinds of code where the scientific result can go wrong and
#: that should therefore be reviewed, automatically or by a person.
REVIEW_CONCERNS = tuple(HazardDecorator)

#: Per concern: what the code does and what to review (the decorator's docstring).
CONCERN_HELP = {HazardDecorator(d.__name__): inspect.getdoc(d) for d in DECORATORS}

#: The decorators plus the derived tables; re-exported unchanged by both package levels.
__all__ = [d.__name__ for d in DECORATORS] + [
    "decorator_of", "DECORATORS", "HazardDecorator", "REVIEW_CONCERNS", "CONCERN_HELP"]
