"""Static scan: which concerns each function is marked with, and which it looks like it has.

Nothing is imported or executed. Every ``*.py`` file under the root is parsed with
:mod:`ast`, so this works on research code that cannot even be imported.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

from ..decorators import Concern, FunctionView
from ..decorators._base import dotted

if TYPE_CHECKING:
    from ..project import Project


@dataclass
class Finding:
    reason: str
    confidence: str


@dataclass
class Record:
    """One top-level function or method."""

    qualname: str
    file: str
    lineno: int
    marked: List[str]
    detected: Dict[str, Finding]
    calls: Set[str] = field(repr=False)
    source: str = field(repr=False, default="")

    @property
    def name(self) -> str:
        return self.qualname.rsplit(".", 1)[-1]

    @property
    def location(self) -> str:
        return f"{self.file}:{self.lineno}"


def _marked(node: ast.AST, concerns: Dict[str, Concern]) -> List[str]:
    """Concern names in the decorator list (``@calculations``, ``@rse.calculations(...)``)."""
    tails = (dotted(d).rsplit(".", 1)[-1] for d in node.decorator_list)
    return [t for t in tails if t in concerns]


def _functions(body, prefix=""):
    """Top-level functions and methods; nested functions belong to their parent."""
    for node in body:
        if isinstance(node, ast.ClassDef):
            yield from _functions(node.body, f"{prefix}{node.name}.")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith(("__", "test_")):
                yield f"{prefix}{node.name}", node


def scan(project: "Project") -> Tuple[List[Record], List[str]]:
    """Scan the project's files for its concerns. Returns (records, parse errors)."""
    concerns, base = project.concerns, project.base
    records, errors = [], []
    for path in project.files():
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        for qualname, node in _functions(tree.body):
            view = FunctionView.of(node)
            detected = {name: Finding(*ev) for name, c in concerns.items() if (ev := c.detect(view))}
            records.append(Record(qualname, path.relative_to(base).as_posix(), node.lineno,
                                  _marked(node, concerns), detected, view.called,
                                  ast.get_source_segment(source, node) or ""))
    _flag_uncalled_validations(records)
    return records, errors


def _flag_uncalled_validations(records: List[Record]) -> None:
    called = set().union(*(r.calls for r in records)) if records else set()
    for rec in records:
        f = rec.detected.get("validation")
        if f and rec.name not in called:
            f.reason += "; never called anywhere in the tree"
            f.confidence = "high"
