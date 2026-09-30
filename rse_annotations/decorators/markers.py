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

A new decorator is a new :class:`HazardDecorator` member plus a function like the ones
below, added to :data:`DECORATORS` at the end of this file. Its docstring is its
help text.
"""

from __future__ import annotations

import inspect
from enum import Enum
from typing import Callable, Dict, Optional

from .registry import REGISTRY, build_info


class HazardDecorator(str, Enum):
    """The review concerns: kinds of code where the scientific result can go wrong.

    One member per decorator below, named like it. A ``str`` subclass, so
    ``HazardDecorator.FUNCTIONAL == "functional"`` and it is written to YAML/JSON as plain text.
    """

    FUNCTIONAL = "functional"
    MAPPING = "mapping"
    DATA_INPUT = "data_input"
    DATA_OUTPUT = "data_output"

    def __str__(self) -> str:   # "functional", not "HazardDecorator.FUNCTIONAL" (also in f-strings)
        return self.value


def _mark(concern: HazardDecorator, fn: Optional[Callable], fields: Optional[Dict[str, str]]):
    """Record ``fn`` under ``concern`` and return it unchanged.

    ``@data_input`` passes the function directly (``fn`` is set).
    ``@data_input(fields=...)`` passes no function, so return a decorator that
    waits for it.
    """
    if fn is None:
        return lambda f: _mark(concern, f, fields)
    info = build_info(concern, fn, fields)
    fn.__rse_decorator__ = info
    REGISTRY.add(info)
    return fn


def functional(fn=None, *, fields=None):
    """Marks a pure mathematical function (deterministic, no I/O, no globals).

    Review the math: wrong formula, wrong denominator, numerical error.
    """
    return _mark(HazardDecorator.FUNCTIONAL, fn, fields)


def mapping(fn=None, *, fields=None):
    """Marks code that maps/transforms one data format or object into another.

    Review for lost or distorted information: dropped rows, units, encoding.
    """
    return _mark(HazardDecorator.MAPPING, fn, fields)


def data_input(fn=None, *, fields=None):
    """Marks a boundary where data enters the system (reads a source/file).

    Review for wrong or mis-parsed data: wrong file, delimiter, missing values.
    """
    return _mark(HazardDecorator.DATA_INPUT, fn, fields)


def data_output(fn=None, *, fields=None):
    """Marks a boundary where data leaves the system (writes a sink/file).

    Review for incomplete or unreproducible results.
    """
    return _mark(HazardDecorator.DATA_OUTPUT, fn, fields)


def decorator_of(func: Callable):
    """Return the :class:`DecoratorInfo` attached to ``func`` (or ``None``)."""
    return getattr(func, "__rse_decorator__", None)


#: The decorators above; add a new one here.
DECORATORS = (functional, mapping, data_input, data_output)

#: The review concerns: kinds of code where the scientific result can go wrong and
#: that should therefore be reviewed, automatically or by a person.
REVIEW_CONCERNS = tuple(HazardDecorator)

#: Per concern: what the code does and what to review (the decorator's docstring).
CONCERN_HELP = {HazardDecorator(d.__name__): inspect.getdoc(d) for d in DECORATORS}
