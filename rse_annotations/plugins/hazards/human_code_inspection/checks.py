"""Automatic checks of the ``human_code_inspection`` plugin (no human involved).

Three families of check:

* **placement** — AST inspection that the decorator is applied to the right kind
  of object and that the body matches the promised role (purity for ``@functional``;
  a real read/write for the boundary decorators);
* **docstring** — the function has a docstring and documents its declared fields;
* **io_success** — running a boundary function actually reads / writes a file.

Every check returns a :class:`CheckResult`; the plugin turns it into a finding.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import re
import tempfile
from dataclasses import dataclass
from typing import List, Optional

from ....decorators.registry import DecoratorInfo
from ....scan import vocabulary as vocab
from ....scan.ast_utils import _called_names, _is_read_name, _is_write_name
from ....decorators.markers import HazardDecorator

# Calls that hint at I/O inside a supposedly pure body.
_IO_HINT_CALLS = vocab.READ_CALLS | vocab.WRITE_CALLS | {"print"}


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

def _get_func_ast(info: DecoratorInfo) -> Optional[ast.AST]:
    """Return the ``FunctionDef`` node for a decorated function, if source is available."""
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


# --------------------------------------------------------------------------- #
# 1. Placement checks
# --------------------------------------------------------------------------- #

def check_placement(info: DecoratorInfo) -> CheckResult:
    """Verify the decorator is applied sensibly for its ``concern``."""
    node = _get_func_ast(info)
    if node is None:
        return CheckResult("placement", "warn",
                           "source unavailable; skipped structural placement check")

    called = _called_names(node)

    if info.concern == HazardDecorator.FUNCTIONAL:
        offenders = sorted(
            n for n in called
            if n in _IO_HINT_CALLS or _is_read_name(n) or _is_write_name(n))
        if offenders:
            return CheckResult(
                "placement", "fail",
                f"@functional should be pure but calls I/O-like functions: {offenders}")
        return CheckResult("placement", "pass", "no I/O detected; looks pure")

    if info.concern == HazardDecorator.DATA_INPUT:
        if any(_is_read_name(n) for n in called):
            return CheckResult("placement", "pass", "contains a read call")
        return CheckResult("placement", "warn",
                           "no obvious read call found in @data_input body")

    if info.concern == HazardDecorator.DATA_OUTPUT:
        if any(_is_write_name(n) for n in called):
            return CheckResult("placement", "pass", "contains a write call")
        return CheckResult("placement", "warn",
                           "no obvious write call found in @data_output body")

    # mapping: no structural requirement beyond being a function.
    return CheckResult("placement", "pass", "mapping function")


# --------------------------------------------------------------------------- #
# 2. Docstring / field documentation checks
# --------------------------------------------------------------------------- #

def check_docstring(info: DecoratorInfo) -> CheckResult:
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
# 3. I/O-success checks for boundary decorators
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


def check_io_success(info: DecoratorInfo, *, fixture=None) -> CheckResult:
    """Run a boundary function in a sandbox and confirm it read / wrote a file.

    Args:
        info: The decorated function (must be ``data_input`` or ``data_output``).
        fixture: Optional callable ``fixture(tmpdir, tracer) -> (args, kwargs)`` that
            prepares inputs (e.g. writes a sample file) and returns call arguments.
            If omitted, the check is reported as ``warn`` (cannot invoke safely).

    Returns:
        A :class:`CheckResult`; ``pass`` only if a matching read/write was observed.
    """
    if info.concern not in (HazardDecorator.DATA_INPUT, HazardDecorator.DATA_OUTPUT):
        return CheckResult("io_success", "pass", "not a boundary function")

    if fixture is None:
        return CheckResult(
            "io_success", "warn",
            "no fixture supplied; cannot exercise I/O (provide one to enable this check)")

    want_read = info.concern == HazardDecorator.DATA_INPUT
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
                           f"@{info.concern} did not {verb} any file when invoked")

