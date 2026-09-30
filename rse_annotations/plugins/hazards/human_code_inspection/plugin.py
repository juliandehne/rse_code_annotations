"""Hazard plugin ``human_code_inspection`` -- *has a human inspected the code that
carries the claim?*

The hazard: generated (or hastily written) research code whose maths no person
has checked. Producers mark what their functions are with the decorators;
this plugin uses the marks to point a reviewer at the code that matters and to
record what the reviewer decided. It is the worked example of the plugin contract
and implements all three modes:

* **analyze** -- one facet per question, all reported as findings:

  ============  =====================================================  ==============
  facet         question                                               imports target
  ============  =====================================================  ==============
  coverage      how much of the code is decorated, what should be?     no
  hazards       which functions carry reproducibility hazards?         no
  uninspected   which ``@functional`` has no *accepted* verdict?       no
  conventions   does each decorator fit the code it sits on?          yes
  math          what formula does each ``@functional`` compute?        yes
  io            do ``@data_input``/``@data_output`` really do I/O?     yes (runs it)
  ============  =====================================================  ==============

* **inspect** -- the interactive review loop
  (:class:`~rse_annotations.inspection.Reviewer`), writing ``inspection.yaml``;
* **generate_tests** -- pytest scaffolds for every decorator
  (:class:`~rse_annotations.testing.TestGenerator`).

Decorator coverage is not a hazard of its own: it is the facet that tells the
reviewer where marks are missing, so the other facets can see the code at all.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, ClassVar, Dict, List, Optional, Sequence, Tuple

from ....decorators.registry import DecoratorInfo
from ....core.findings import AnalysisResult, Finding
from ....core.plugin import Plugin
from . import checks as _checks
from ....inspection.formula import FormulaResult, infer_formula
from ....inspection import Reviewer, VerdictStore
from ....inspection.verdicts import Verdict
from ....scan import CRITICAL_HAZARDS, CoverageReport
from ....testing import TestGenerator
from ....decorators.markers import HazardDecorator

#: Every facet, in reporting order. The first three never import the target.
FACETS: Tuple[str, ...] = ("coverage", "hazards", "uninspected", "conventions", "math", "io")
STATIC_FACETS: Tuple[str, ...] = ("coverage", "hazards", "uninspected")

_SEVERITY = {"pass": "info", "warn": "warn", "fail": "fail"}


@dataclass
class InspectionData:
    """The native payload of :meth:`HumanCodeInspection.analyze` (``AnalysisResult.data``).

    ``coverage`` makes the markdown renderer print the full coverage report.
    """

    coverage: Optional[CoverageReport] = None
    formulas: List[FormulaResult] = field(default_factory=list)
    verdicts: List[Verdict] = field(default_factory=list)


def _from_check(info: DecoratorInfo, check: "_checks.CheckResult") -> Finding:
    return Finding(rule=check.name, severity=_SEVERITY[check.status], message=check.message,
                   function=info.qualname, location=info.location)


def _same_file(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


class HumanCodeInspection(Plugin):
    """Points a human at decorated code, records their verdicts, reports what is unchecked.

    Args:
        facets: The :data:`FACETS` to analyse (default: all). ``STATIC_FACETS`` never
            import the target.
        fixtures: For the ``io`` facet: qualname or name ->
            ``fixture(tmpdir, tracer) -> (args, kwargs)``. A boundary without a fixture
            is not invoked and yields a ``warn``.
    """

    name: ClassVar[str] = "human_code_inspection"
    description: ClassVar[str] = ("has a human inspected the decorated code? coverage, "
                                  "hazards, unreviewed maths, conventions, I/O")
    question: ClassVar[str] = "has a human checked the code that carries the claim?"
    imports_target: ClassVar[bool] = True

    def __init__(self, facets: Optional[Sequence[str]] = None, *,
                 fixtures: Optional[Dict[str, Callable]] = None) -> None:
        unknown = set(facets or ()) - set(FACETS)
        if unknown:
            raise ValueError(f"unknown facet(s) {sorted(unknown)}; choose from {FACETS}")
        self.facets = tuple(f for f in FACETS if facets is None or f in facets)
        self.fixtures = fixtures or {}

    # ---- hazard analysis ------------------------------------------------ #
    def analyze(self, target) -> AnalysisResult:
        data = InspectionData()
        findings: List[Finding] = []
        if set(self.facets) & {"coverage", "hazards", "uninspected"}:
            data.coverage = target.static_scan()
        if "coverage" in self.facets:
            findings += self.coverage_findings(data.coverage)
        if "hazards" in self.facets:
            findings += self.hazard_findings(data.coverage)
        if "uninspected" in self.facets:
            data.verdicts = VerdictStore.for_target(target).load()
            findings += self.uninspected_findings(data.coverage, data.verdicts)
        wants_import = [f for f in ("conventions", "math", "io") if f in self.facets]
        if wants_import:
            infos = target.decorated()
            for info in infos:
                if "conventions" in self.facets:
                    findings += self.convention_findings(info)
                if "math" in self.facets and info.concern == HazardDecorator.FUNCTIONAL:
                    res = infer_formula(info)
                    data.formulas.append(res)
                    findings.append(self.formula_finding(info, res))
                if "io" in self.facets and info.concern in (HazardDecorator.DATA_INPUT, HazardDecorator.DATA_OUTPUT):
                    findings.append(self.io_finding(info))
        return self.result(findings, data=data)

    @staticmethod
    def coverage_findings(report: CoverageReport) -> List[Finding]:
        findings = [Finding(
            "coverage", "info",
            f"{len(report.decorated)}/{len(report.eligible)} eligible functions decorated "
            f"({report.coverage:.0%}) across {report.files_scanned} file(s)",
            evidence={"coverage": report.coverage, "files": report.files_scanned})]
        for rec in report.candidates:
            findings.append(Finding(
                "candidate", "info", f"looks like @{rec.suggested}: {rec.reason}",
                function=f"{rec.module}.{rec.qualname}", location=rec.location,
                evidence={"suggested": rec.suggested, "confidence": rec.confidence}))
        for path, err in report.parse_errors:
            findings.append(Finding("parse_error", "warn", err, location=path))
        return findings

    @staticmethod
    def hazard_findings(report: CoverageReport) -> List[Finding]:
        """Reproducibility-critical hazards are ``warn``, the rest ``info``; inherited
        ones are marked ``indirect`` in the evidence."""
        return [Finding(f"hazard.{hz.kind}", "warn" if hz.kind in CRITICAL_HAZARDS else "info",
                        hz.reason, function=f"{rec.module}.{rec.qualname}", location=rec.location,
                        evidence={"confidence": hz.confidence, "indirect": hz.indirect})
                for rec in report.hazardous for hz in rec.hazards]

    @staticmethod
    def uninspected_findings(report: CoverageReport, verdicts: List[Verdict]) -> List[Finding]:
        """Every ``@functional`` without an accepted verdict: ``fail`` if a human
        declined it, ``warn`` if nobody has decided yet."""
        findings = []
        for rec in report.decorated:
            if rec.concern != HazardDecorator.FUNCTIONAL:
                continue
            verdict = next((v for v in verdicts if v.function == rec.name
                            and _same_file(v.location.rsplit(":", 1)[0], rec.file)), None)
            state = verdict.verdict if verdict else "not reviewed"
            if state == "accepted":
                continue
            findings.append(Finding(
                "uninspected", "fail" if state == "declined" else "warn",
                "a reviewer declined this @functional" if state == "declined"
                else f"@functional has no accepted verdict ({state}); run the human inspection",
                function=f"{rec.module}.{rec.qualname}", location=rec.location,
                evidence={"verdict": state}))
        return findings

    @staticmethod
    def convention_findings(info: DecoratorInfo) -> List[Finding]:
        """Placement (a ``@functional`` does no I/O, a boundary really does) and, for
        non-functional concerns, that the docstring documents the declared fields."""
        found = [_from_check(info, _checks.check_placement(info))]
        if info.concern != HazardDecorator.FUNCTIONAL:
            found.append(_from_check(info, _checks.check_docstring(info)))
        return found

    @staticmethod
    def formula_finding(info: DecoratorInfo, res: FormulaResult) -> Finding:
        if res.any_formula:
            formula = (res.ast_forms or [res.sympy_form or res.latexify_form])[0]
            return Finding("formula", "info", f"inferred: {formula}",
                           function=info.qualname, location=info.location,
                           evidence={"ast": res.ast_forms, "sympy": res.sympy_form,
                                     "latex": res.sympy_latex or res.latexify_form})
        return Finding("formula", "warn", "no closed-form formula could be inferred; "
                       "review the source", function=info.qualname, location=info.location,
                       evidence={"notes": res.notes})

    def io_finding(self, info: DecoratorInfo) -> Finding:
        fixture = self.fixtures.get(info.qualname) or self.fixtures.get(info.name)
        return _from_check(info, _checks.check_io_success(info, fixture=fixture))

    # ---- human inspection ----------------------------------------------- #
    def inspect(self, target, *, input_fn: Callable[[str], str] = input,
                output_fn: Callable[[str], None] = print) -> List[Verdict]:
        """Step through every ``@functional`` and record accept / decline / skip."""
        reviewer = Reviewer(VerdictStore.for_target(target), input_fn=input_fn,
                            output_fn=output_fn)
        return reviewer.review(target.decorated())

    # ---- test generation ------------------------------------------------ #
    def generate_tests(self, target, *, out_dir=None,
                       output_fn: Callable[[str], None] = print):
        """Pattern-based pytest scaffolds for every decorator (``<target>/tests/``)."""
        return [sf.path for sf in TestGenerator(target, out_dir).write(output_fn)]
