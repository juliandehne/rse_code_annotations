"""The legacy runner: a per-function :class:`Report` built on :class:`~rse_annotations.core.audit.Audit`.

.. deprecated::
    :class:`Runner` predates the object model. It is kept so existing callers
    (tests, examples, the lni_study testbed) keep working, but it no longer has an
    engine of its own: it builds a :class:`~rse_annotations.core.target.TargetProject`
    from module names, runs the ``conventions``, ``io`` and ``math`` facets of the
    ``human_code_inspection`` plugin through an ``Audit``, and regroups the findings per
    function. New code should use ``Audit`` directly.

Fixtures for the I/O-success checks are supplied by the caller as a mapping from
``qualname`` to a ``fixture(tmpdir, tracer) -> (args, kwargs)`` callable. A boundary
function without a fixture yields a ``warn`` (cannot be safely invoked).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
import warnings
from typing import Callable, Dict, List, Optional, Union

from .decorators.registry import DecoratorInfo
from .core.audit import Audit, AuditReport
from .core.catalog import PluginCatalog
from .core.target import TargetProject
from .plugins.hazards.human_code_inspection import checks as _checks
from .inspection.formula import FormulaResult, render_formula
from .inspection.snippets import Snippet, extract_snippet
from .plugins.hazards.human_code_inspection import HumanCodeInspection
from .decorators.markers import HazardDecorator

_STATUS = {"info": "pass", "warn": "warn", "fail": "fail"}
#: The order the per-function checks are reported in.
_ORDER = {"placement": 0, "docstring": 1, "io_success": 2}


@dataclass
class FunctionReport:
    concern: str
    name: str
    qualname: str
    location: str
    checks: List[_checks.CheckResult] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(c.status == "fail" for c in self.checks):
            return "fail"
        if any(c.status == "warn" for c in self.checks):
            return "warn"
        return "pass"


@dataclass
class Report:
    functions: List[FunctionReport] = field(default_factory=list)
    snippets: List[Snippet] = field(default_factory=list)
    formulas: List[FormulaResult] = field(default_factory=list)

    @classmethod
    def from_audit(cls, infos: List[DecoratorInfo], audit: AuditReport) -> "Report":
        """Regroup an audit's findings per decorated function, in discovery order."""
        by_fn: Dict[str, List[_checks.CheckResult]] = {i.qualname: [] for i in infos}
        try:
            result = audit.result(HumanCodeInspection.name)
        except KeyError:
            result = None
        for f in result.findings if result else ():
            if f.rule in _ORDER and f.function in by_fn:
                by_fn[f.function].append(_checks.CheckResult(
                    f.rule, _STATUS[f.severity], f.message))
        report = cls(functions=[
            FunctionReport(i.concern, i.name, i.qualname, i.location,
                           sorted(by_fn[i.qualname], key=lambda c: _ORDER.get(c.name, 9)))
            for i in infos])
        functional = [i for i in infos if i.concern == HazardDecorator.FUNCTIONAL]
        report.snippets = [extract_snippet(i) for i in functional]
        if result is not None and result.data is not None:
            report.formulas = list(result.data.formulas)
        return report

    # ---- aggregate accessors ------------------------------------------- #
    @property
    def counts(self) -> Dict[str, int]:
        c = {"pass": 0, "warn": 0, "fail": 0}
        for fr in self.functions:
            c[fr.status] += 1
        return c

    @property
    def ok(self) -> bool:
        return all(fr.status != "fail" for fr in self.functions)

    def to_dict(self) -> dict:
        return {
            "counts": self.counts,
            "functions": [
                {
                    "concern": fr.concern,
                    "name": fr.name,
                    "qualname": fr.qualname,
                    "location": fr.location,
                    "status": fr.status,
                    "checks": [asdict(c) for c in fr.checks],
                }
                for fr in self.functions
            ],
            "functional_review": {
                "snippets": [
                    {
                        "name": s.name,
                        "location": s.location,
                        "signature": s.signature,
                    }
                    for s in self.snippets
                ],
                "formulas": [
                    {
                        "name": f.name,
                        "location": f.location,
                        "ast_forms": f.ast_forms,
                        "sympy_form": f.sympy_form,
                        "sympy_latex": f.sympy_latex,
                        "latexify_form": f.latexify_form,
                        "notes": f.notes,
                    }
                    for f in self.formulas
                ],
            },
        }


class Runner:
    """Deprecated: discover -> check -> snippets/formulas, via :class:`Audit`."""

    def __init__(
        self,
        target: Union[str, List[str]],
        *,
        fixtures: Optional[Dict[str, Callable]] = None,
        infer_formulas: bool = True,
    ) -> None:
        warnings.warn("Runner is deprecated; use Audit(TargetProject.from_modules(...))",
                      DeprecationWarning, stacklevel=2)
        self.targets = [target] if isinstance(target, str) else list(target)
        self.fixtures = fixtures or {}
        self.infer_formulas = infer_formulas

    def audit(self) -> Audit:
        facets = ["conventions", "io"] + (["math"] if self.infer_formulas else [])
        plugin = HumanCodeInspection(facets, fixtures=self.fixtures)
        return Audit(TargetProject.from_modules(self.targets), catalog=PluginCatalog(),
                     plugins=[plugin])

    def run(self) -> Report:
        audit = self.audit()
        return Report.from_audit(audit.target.decorated(), audit.run())


# --------------------------------------------------------------------------- #
# Human-readable rendering
# --------------------------------------------------------------------------- #

_ICON = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}


def render_text(report: Report, *, show_snippets: bool = True) -> str:
    lines: List[str] = []
    c = report.counts
    lines.append(f"rse_code_annotations report -- {c['pass']} pass, "
                 f"{c['warn']} warn, {c['fail']} fail\n")

    for fr in report.functions:
        lines.append(f"[{_ICON[fr.status]}] @{fr.concern} {fr.name}  ({fr.location})")
        for chk in fr.checks:
            lines.append(f"    - {_ICON[chk.status]} {chk.name}: {chk.message}")
        lines.append("")

    # Functional review section
    if report.snippets:
        lines.append("=" * 70)
        lines.append("@functional review -- inspect these snippets for mathematical correctness:")
        lines.append("")

    # Inferred formulas (formal-methods / symbolic inspection)
    if report.formulas:
        lines.append("-" * 70)
        lines.append("Inferred formulas (for human inspection -- NOT a correctness proof):")
        lines.append("")
        for fr in report.formulas:
            lines.append(render_formula(fr))
            lines.append("")

    if report.snippets:
        for s in report.snippets:
            lines.append(f"--- {s.signature}  ({s.location}) ---")
            if show_snippets:
                for src_line in s.source.splitlines():
                    lines.append(f"    {src_line}")
            lines.append("")

    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2)
