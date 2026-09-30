"""Shared AST helpers: call names, file I/O, decorator detection.

Used by the static scan (:mod:`rse_annotations.scan`) and by the per-decorator
checks (:mod:`rse_annotations.plugins.hazards.human_code_inspection.checks`).
Nothing here imports the target.
"""

from __future__ import annotations

import ast
from typing import Dict, List, Optional, Tuple

from ..decorators.markers import REVIEW_CONCERNS, HazardDecorator
from . import vocabulary as vocab

def _is_read_name(name: str) -> bool:
    return name in vocab.READ_CALLS or name.startswith(vocab.READ_PREFIXES)


def _is_write_name(name: str) -> bool:
    return name in vocab.WRITE_CALLS or name.startswith(vocab.WRITE_PREFIXES)


def _called_names(node: ast.AST) -> set:
    """Collect the set of function/attribute names called anywhere under ``node``."""
    names = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                names.add(f.id)
            elif isinstance(f, ast.Attribute):
                names.add(f.attr)
    return names


# --------------------------------------------------------------------------- #
# Syntactic decorator detection
# --------------------------------------------------------------------------- #

def _dotted(node: ast.AST) -> str:
    """Render a decorator expression as a dotted name (``a.b.c``), best effort."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    return ""


def _alias_map(tree: ast.Module) -> Dict[str, HazardDecorator]:
    """Map the local names that refer to our decorators onto their kind.

    Handles ``from rse_annotations import functional``, ``... import functional as pure``
    and ``import rse_annotations`` (used as ``@rse_annotations.functional``).
    """
    aliases: Dict[str, HazardDecorator] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "rse_annotations" or mod.startswith("rse_annotations."):
                for a in node.names:
                    if a.name in REVIEW_CONCERNS:
                        aliases[a.asname or a.name] = HazardDecorator(a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "rse_annotations":
                    # qualified use: <local>.functional
                    for kind in REVIEW_CONCERNS:
                        aliases[f"{a.asname or a.name}.{kind}"] = kind
    return aliases


def _decorator_concern(node: ast.AST, aliases: Dict[str, HazardDecorator]) -> Optional[HazardDecorator]:
    """Return the rse decorator applied to ``node``, if any (bare or called form)."""
    for dec in getattr(node, "decorator_list", []):
        name = _dotted(dec)
        if name in aliases:
            return aliases[name]
        # Fall back to the bare kind name even without a recognised import: research
        # code is often copied around, and a literal @functional is unambiguous here.
        tail = name.rsplit(".", 1)[-1]
        if tail in REVIEW_CONCERNS:
            return HazardDecorator(tail)
    return None


# --------------------------------------------------------------------------- #
# Candidate inference
# --------------------------------------------------------------------------- #

def _call_name(call: ast.Call) -> Optional[str]:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _open_mode(call: ast.Call) -> str:
    """The mode string passed to ``open(...)`` -- ``"r"`` if not given literally."""
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant) \
            and isinstance(call.args[1].value, str):
        return call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant) \
                and isinstance(kw.value.value, str):
            return kw.value.value
    return "r"


def _file_io_calls(node: ast.AST) -> Tuple[List[str], List[str]]:
    """Split the calls in ``node`` into (reads, writes), ignoring in-memory look-alikes.

    ``open`` is resolved by its *mode*: ``open(p, "w")`` is a write, not a read.
    """
    reads, writes = set(), set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        name = _call_name(n)
        if not name or name in vocab.NOT_FILE_IO:
            continue
        if name == "open":
            mode = _open_mode(n)
            target = writes if any(c in mode for c in "wxa+") else reads
            target.add(f'open("{mode}")')
        elif _is_write_name(name):
            writes.add(name)
        elif _is_read_name(name):
            reads.add(name)
    return sorted(reads), sorted(writes)


def _returns_a_value(node: ast.AST) -> bool:
    """True if the body has a ``return <expr>`` (a bare ``return`` does not count)."""
    for n in ast.walk(node):
        if isinstance(n, ast.Return) and n.value is not None:
            return True
        if isinstance(n, (ast.Yield, ast.YieldFrom)):
            return True
    return False


def _param_names(node: ast.AST) -> List[str]:
    a = node.args
    names = [p.arg for p in (list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs))]
    if a.vararg:
        names.append(a.vararg.arg)
    if a.kwarg:
        names.append(a.kwarg.arg)
    return names
