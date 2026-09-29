"""Analyzers over annotated functions: the maths, the I/O boundaries, the conventions."""

from __future__ import annotations

from typing import Callable, ClassVar, Dict, List, Optional, Tuple

from .. import checks as _checks
from ..findings import Finding
from ..formula import FormulaResult, infer_formula
from ..registry import AnnotationInfo
from .base import AnnotationAnalyzer

_SEVERITY = {"pass": "info", "warn": "warn", "fail": "fail"}


def _from_check(info: AnnotationInfo, check: _checks.CheckResult) -> Finding:
    return Finding(rule=check.name, severity=_SEVERITY[check.status], message=check.message,
                   function=info.qualname, location=info.location)


class MathAnalyzer(AnnotationAnalyzer):
    """Infers the formula behind every ``@functional`` so a human can check the maths.

    Uses the AST renderer always, SymPy and latexify when the ``[formula]`` extra is
    installed. A function whose formula cannot be inferred is a ``warn``: it has to
    be reviewed from source alone. ``data`` is the list of
    :class:`~rse_annotations.formula.FormulaResult`.
    """

    name = "math"
    description = "infer the formula of each @functional for human review"
    kinds: ClassVar[Tuple[str, ...]] = ("functional",)

    def analyze_function(self, info: AnnotationInfo) -> List[Finding]:
        res = infer_formula(info)
        if res.any_formula:
            formula = (res.ast_forms or [res.sympy_form or res.latexify_form])[0]
            return [Finding("formula", "info", f"inferred: {formula}",
                            function=info.qualname, location=info.location,
                            evidence={"ast": res.ast_forms, "sympy": res.sympy_form,
                                      "latex": res.sympy_latex or res.latexify_form})]
        return [Finding("formula", "warn", "no closed-form formula could be inferred; "
                        "review the source", function=info.qualname, location=info.location,
                        evidence={"notes": res.notes})]

    def collect(self, infos: List[AnnotationInfo]) -> List[FormulaResult]:
        return [infer_formula(i) for i in infos]


class IOAnalyzer(AnnotationAnalyzer):
    """Exercises every ``@data_input`` / ``@data_output`` and checks it really reads / writes.

    Runs the function in a temporary directory under an ``open()`` tracer. A
    function is only invoked when a fixture is supplied for it -- a mapping from
    qualname or name to ``fixture(tmpdir, tracer) -> (args, kwargs)``; without one
    the finding is a ``warn``.
    """

    name = "io"
    description = "run @data_input/@data_output with fixtures and trace the file I/O"
    when = "test"
    kinds: ClassVar[Tuple[str, ...]] = ("data_input", "data_output")

    def __init__(self, fixtures: Optional[Dict[str, Callable]] = None) -> None:
        self.fixtures = fixtures or {}

    def analyze_function(self, info: AnnotationInfo) -> List[Finding]:
        fixture = self.fixtures.get(info.qualname) or self.fixtures.get(info.name)
        return [_from_check(info, _checks.check_io_success(info, fixture=fixture))]


class ConventionAnalyzer(AnnotationAnalyzer):
    """Checks that each annotation fits the code it sits on.

    Placement: a ``@functional`` body does no I/O, a boundary really reads or
    writes. Docstring: non-functional annotations document their declared fields.
    """

    name = "conventions"
    description = "annotation placement (purity, real boundaries) and docstrings"

    def analyze_function(self, info: AnnotationInfo) -> List[Finding]:
        found = [_from_check(info, _checks.check_placement(info))]
        if info.kind != "functional":
            found.append(_from_check(info, _checks.check_docstring(info)))
        return found
