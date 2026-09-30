"""Reflection metadata and the process-global registry of annotated functions.

Every annotation decorator (see :mod:`rse_annotations.annotations`) records an
:class:`AnnotationInfo` on the function it decorates *and* appends it to
:data:`REGISTRY`, so the runner can discover annotated functions simply by
importing the target package.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

#: The four roles a function can be annotated with.
KINDS = ("functional", "mapping", "data_input", "data_output")

#: One-line guidance per kind: what it means and when to reach for it. Used by the
#: ``rse-annotations kinds`` command so a user can choose which annotation to apply.
KIND_HELP = {
    "functional": ("a pure mathematical function -- deterministic, no I/O, no globals. "
                   "Its formula can be inferred and it can be differentially verified."),
    "mapping": ("transforms one in-memory data shape/format into another "
                "(parsing, encoding, reshaping). Not an I/O boundary."),
    "data_input": "a boundary where data enters the system: reads a file / source.",
    "data_output": "a boundary where data leaves the system: writes a file / sink.",
}


@dataclass
class AnnotationInfo:
    """Metadata attached to every annotated function.

    Attributes:
        kind: One of :data:`KINDS`.
        func: The (undecorated) function object.
        qualname: Module-qualified name, e.g. ``pkg.mod.transform``.
        module: Defining module's ``__name__``.
        file: Absolute path to the source file.
        lineno: 1-based line of the ``def`` statement.
        fields: Optional declared field schema (name -> description/type) used to
            cross-check the docstring for non-functional annotations.
    """

    kind: str
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
    """An ordered, de-duplicated collection of :class:`AnnotationInfo`."""

    def __init__(self) -> None:
        self._items: List[AnnotationInfo] = []
        self._seen: set = set()

    def add(self, info: AnnotationInfo) -> None:
        key = (info.module, info.qualname, info.lineno)
        if key in self._seen:
            return
        self._seen.add(key)
        self._items.append(info)

    def all(self) -> List[AnnotationInfo]:
        return list(self._items)

    def of_kind(self, kind: str) -> List[AnnotationInfo]:
        return [i for i in self._items if i.kind == kind]

    def clear(self) -> None:
        self._items.clear()
        self._seen.clear()

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)


#: Populated at import time as annotated modules are loaded.
REGISTRY = Registry()


def build_info(kind: str, func: Callable, fields: Optional[Dict[str, str]]) -> AnnotationInfo:
    """Construct an :class:`AnnotationInfo` by introspecting ``func``."""
    try:
        source_file = inspect.getsourcefile(func) or "<unknown>"
    except TypeError:
        source_file = "<unknown>"
    try:
        _, lineno = inspect.getsourcelines(func)
    except (OSError, TypeError):
        lineno = getattr(func, "__code__", None) and func.__code__.co_firstlineno or 0
    return AnnotationInfo(
        kind=kind,
        func=func,
        qualname=getattr(func, "__qualname__", func.__name__),
        module=getattr(func, "__module__", "<unknown>"),
        file=source_file,
        lineno=lineno,
        fields=fields,
    )
