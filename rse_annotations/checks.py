"""Validation checks used by the runner.

Three families of check:

* **placement** — AST inspection that the annotation is applied to the right kind
  of object and that the body matches the promised role (purity for ``@functional``;
  a real read/write for the boundary annotations);
* **docstring** — the function has a docstring and documents its declared fields;
* **io_success** — running a boundary function actually reads / writes a file.

Every check returns a :class:`CheckResult` so the runner can aggregate them.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import io
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

from .registry import AnnotationInfo

# Calls that indicate file / stream I/O — used by the purity and boundary lints.
_READ_CALLS = {"open", "read", "read_text", "read_bytes", "load", "loads", "readlines",
               "readline", "recv", "input"}
_WRITE_CALLS = {"write", "writelines", "write_text", "write_bytes", "dump", "dumps",
                "save", "to_csv", "to_json", "send", "flush"}
_IO_HINT_CALLS = _READ_CALLS | _WRITE_CALLS | {"print"}


@dataclass
class CheckResult:
    """Outcome of a single check.

    Attributes:
        name: Short check identifier, e.g. ``"placement"``.
        status: ``"pass"``, ``"warn"`` or ``"fail"``.
        message: Human-readable explanation.
    """

    name: str
    status: str  # "pass" | "warn" | "fail"
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status != "fail"


# --------------------------------------------------------------------------- #
# AST helpers
# --------------------------------------------------------------------------- #

def _get_func_ast(info: AnnotationInfo) -> Optional[ast.AST]:
    """Return the ``FunctionDef`` node for an annotated function, if source is available."""
    try:
        src = inspect.getsource(info.func)
    except (OSError, TypeError):
        return None
    src = _dedent(src)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    return None


def _dedent(src: str) -> str:
    import textwrap
    return textwrap.dedent(src)


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
# 1. Placement checks
# --------------------------------------------------------------------------- #

def check_placement(info: AnnotationInfo) -> CheckResult:
    """Verify the annotation is applied sensibly for its ``kind``."""
    node = _get_func_ast(info)
    if node is None:
        return CheckResult("placement", "warn",
                           "source unavailable; skipped structural placement check")

    called = _called_names(node)

    if info.kind == "functional":
        offenders = sorted(called & _IO_HINT_CALLS)
        if offenders:
            return CheckResult(
                "placement", "fail",
                f"@functional should be pure but calls I/O-like functions: {offenders}")
        return CheckResult("placement", "pass", "no I/O detected; looks pure")

    if info.kind == "data_input":
        if called & _READ_CALLS:
            return CheckResult("placement", "pass", "contains a read call")
        return CheckResult("placement", "warn",
                           "no obvious read call found in @data_input body")

    if info.kind == "data_output":
        if called & _WRITE_CALLS:
            return CheckResult("placement", "pass", "contains a write call")
        return CheckResult("placement", "warn",
                           "no obvious write call found in @data_output body")

    # mapping: no structural requirement beyond being a function.
    return CheckResult("placement", "pass", "mapping function")


# --------------------------------------------------------------------------- #
# 2. Docstring / field documentation checks
# --------------------------------------------------------------------------- #

def check_docstring(info: AnnotationInfo) -> CheckResult:
    """Require a docstring, and that every declared field is mentioned in it."""
    doc = inspect.getdoc(info.func)
    if not doc or not doc.strip():
        return CheckResult("docstring", "fail", "missing docstring (pythondoc)")

    if info.fields:
        missing = [name for name in info.fields
                   if not re.search(rf"\b{re.escape(name)}\b", doc)]
        if missing:
            return CheckResult(
                "docstring", "fail",
                f"docstring does not document fields: {missing}")
        return CheckResult("docstring", "pass",
                           f"docstring documents all {len(info.fields)} declared fields")

    return CheckResult("docstring", "pass", "docstring present")


# --------------------------------------------------------------------------- #
# 3. I/O-success checks for boundary annotations
# --------------------------------------------------------------------------- #

class _OpenTracer:
    """Context manager that records paths+modes passed to ``builtins.open``."""

    def __init__(self) -> None:
        self.reads: List[str] = []
        self.writes: List[str] = []
        self._orig = builtins.open

    def __enter__(self) -> "_OpenTracer":
        tracer = self

        def traced_open(file, mode="r", *args, **kwargs):
            m = mode if isinstance(mode, str) else "r"
            if any(c in m for c in "wxa") or "+" in m:
                tracer.writes.append(str(file))
            else:
                tracer.reads.append(str(file))
            return tracer._orig(file, mode, *args, **kwargs)

        builtins.open = traced_open
        return self

    def __exit__(self, *exc) -> None:
        builtins.open = self._orig


def check_io_success(info: AnnotationInfo, *, fixture=None) -> CheckResult:
    """Run a boundary function in a sandbox and confirm it read / wrote a file.

    Args:
        info: The annotated function (must be ``data_input`` or ``data_output``).
        fixture: Optional callable ``fixture(tmpdir, tracer) -> (args, kwargs)`` that
            prepares inputs (e.g. writes a sample file) and returns call arguments.
            If omitted, the check is reported as ``warn`` (cannot invoke safely).

    Returns:
        A :class:`CheckResult`; ``pass`` only if a matching read/write was observed.
    """
    if info.kind not in ("data_input", "data_output"):
        return CheckResult("io_success", "pass", "not a boundary function")

    if fixture is None:
        return CheckResult(
            "io_success", "warn",
            "no fixture supplied; cannot exercise I/O (provide one to enable this check)")

    want_read = info.kind == "data_input"
    with tempfile.TemporaryDirectory() as tmp:
        with _OpenTracer() as tracer:
            try:
                args, kwargs = fixture(tmp, tracer)
                info.func(*(args or ()), **(kwargs or {}))
            except Exception as exc:  # noqa: BLE001
                return CheckResult("io_success", "fail",
                                   f"function raised while exercising I/O: {exc!r}")

        observed = tracer.reads if want_read else tracer.writes
        verb = "read" if want_read else "wrote"
        if observed:
            return CheckResult("io_success", "pass",
                               f"{verb} {len(observed)} file(s): {observed}")
        return CheckResult("io_success", "fail",
                           f"@{info.kind} did not {verb} any file when invoked")


def all_checks(info: AnnotationInfo, *, fixture=None) -> List[CheckResult]:
    """Run every check appropriate for ``info``'s kind."""
    results = [check_placement(info)]
    if info.kind != "functional":
        results.append(check_docstring(info))
    if info.kind in ("data_input", "data_output"):
        results.append(check_io_success(info, fixture=fixture))
    return results
