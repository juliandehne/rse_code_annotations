"""Reflection metadata and the process-global registry of decorated functions.

Every marker decorator (see :mod:`rse_annotations.decorators`) records an
:class:`DecoratorInfo` on the function it decorates *and* appends it to
:data:`REGISTRY`, so the runner can discover decorated functions simply by
importing the target package.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class DecoratorInfo:
    """Metadata attached to every decorated function.

    Attributes:
        concern: One of :data:`~rse_annotations.decorators.markers.REVIEW_CONCERNS`.
        func: The (undecorated) function object.
        qualname: Module-qualified name, e.g. ``pkg.mod.transform``.
        module: Defining module's ``__name__``.
        file: Absolute path to the source file.
        lineno: 1-based line of the ``def`` statement.
        fields: Optional declared field schema (name -> description/type) used to
            cross-check the docstring for non-functional decorators.
    """

    concern: str
    func: Callable
    qualname: str
    module: str
    file: str
    lineno: int
    fields: Optional[Dict[str, str]] = None

    @property
    def name(self) -> str:
        return self.func.__name__

    @property
    def location(self) -> str:
        return f"{self.file}:{self.lineno}"


class Registry:
    """An ordered, de-duplicated collection of :class:`DecoratorInfo`."""

    def __init__(self) -> None:
        # A dict keeps insertion order, and its keys rule out duplicates.
        self._items: Dict[tuple, DecoratorInfo] = {}

    def add(self, info: DecoratorInfo) -> None:
        # setdefault keeps the first entry if the same function is added again.
        self._items.setdefault((info.module, info.qualname, info.lineno), info)

    def all(self) -> List[DecoratorInfo]:
        return list(self._items.values())

    def of_concern(self, concern: str) -> List[DecoratorInfo]:
        return [i for i in self._items.values() if i.concern == concern]

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items.values())


#: Populated at import time as decorated modules are loaded.
REGISTRY = Registry()


def build_info(concern: str, func: Callable, fields: Optional[Dict[str, str]]) -> DecoratorInfo:
    """Construct an :class:`DecoratorInfo` by introspecting ``func``."""
    try:
        source_file = inspect.getsourcefile(func) or "<unknown>"
    except TypeError:
        source_file = "<unknown>"
    return DecoratorInfo(
        concern=concern,
        func=func,
        qualname=getattr(func, "__qualname__", func.__name__),
        module=getattr(func, "__module__", "<unknown>"),
        file=source_file,
        lineno=func.__code__.co_firstlineno,
        fields=fields,
    )
