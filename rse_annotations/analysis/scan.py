"""Static scan: which concerns each function is marked with, and which it looks like it has.

Nothing is imported or executed. Every ``*.py`` file under the root is parsed with
:mod:`ast`, so this works on research code that cannot even be imported.
"""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple

from ..decorators import CONCERNS, FunctionView
from ..decorators._base import dotted

SKIP_DIRS = {"__pycache__", "venv", "env", "node_modules", "tests", "build", "dist"}


@dataclass
class Finding:
    reason: str
    confidence: str
    indirect: bool = False   # inherited through the call graph


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


def _marked(node: ast.AST) -> List[str]:
    """Concern names in the decorator list (``@calculations``, ``@rse.calculations(...)``)."""
    tails = (dotted(d).rsplit(".", 1)[-1] for d in node.decorator_list)
    return [t for t in tails if t in CONCERNS]


def _functions(body, prefix=""):
    """Top-level functions and methods; nested functions belong to their parent."""
    for node in body:
        if isinstance(node, ast.ClassDef):
            yield from _functions(node.body, f"{prefix}{node.name}.")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith(("__", "test_")):
                yield f"{prefix}{node.name}", node


def _python_files(root: Path):
    if root.is_file():
        yield root
        return
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f.endswith(".py") and not f.startswith("test_") and f not in ("conftest.py", "setup.py"):
                yield Path(dirpath) / f


def scan(root) -> Tuple[List[Record], List[str]]:
    """Scan ``root`` (a directory or one file). Returns (records, parse errors)."""
    root = Path(root).resolve()
    base = root.parent if root.is_file() else root
    records, errors = [], []
    for path in _python_files(root):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        for qualname, node in _functions(tree.body):
            view = FunctionView.of(node)
            detected = {name: Finding(*ev) for name, c in CONCERNS.items() if (ev := c.detect(view))}
            records.append(Record(qualname, path.relative_to(base).as_posix(), node.lineno,
                                  _marked(node), detected, view.called,
                                  ast.get_source_segment(source, node) or ""))
    _propagate(records)
    _flag_uncalled_validations(records)
    return records, errors


def _propagate(records: List[Record]) -> None:
    """Callers inherit contagious concerns (matched by bare function name, so marked indirect)."""
    contagious = [n for n, c in CONCERNS.items() if c.contagious]
    changed = True
    while changed:
        changed = False
        carriers = {k: {r.name for r in records if k in r.detected} for k in contagious}
        for rec in records:
            for k in contagious:
                via = sorted((rec.calls & carriers[k]) - {rec.name})
                if k not in rec.detected and via:
                    rec.detected[k] = Finding(f"inherits from {', '.join(via[:2])}", "medium", True)
                    changed = True


def _flag_uncalled_validations(records: List[Record]) -> None:
    called = set().union(*(r.calls for r in records)) if records else set()
    for rec in records:
        f = rec.detected.get("validation")
        if f and rec.name not in called:
            f.reason += "; never called anywhere in the tree"
            f.confidence = "high"
