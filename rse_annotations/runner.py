"""The runner: discover annotated functions, check them, and report.

Pulls together discovery, the checks, and the (optional) Fable-assisted
``@functional`` review into a single :class:`Report`.

Fixtures for the I/O-success checks are supplied by the caller as a mapping from
``qualname`` to a ``fixture(tmpdir, tracer) -> (args, kwargs)`` callable. A boundary
function without a fixture yields a ``warn`` (cannot be safely invoked).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional

from . import checks as _checks
from .discovery import discover
from .fable import FableStatus, Snippet, functional_review
from .formula import FormulaResult, infer_formula, render_formula
from .registry import AnnotationInfo


@dataclass
class FunctionReport:
    kind: str
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
    fable: Optional[FableStatus] = None

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
                    "kind": fr.kind,
                    "name": fr.name,
                    "qualname": fr.qualname,
                    "location": fr.location,
                    "status": fr.status,
                    "checks": [asdict(c) for c in fr.checks],
                }
                for fr in self.functions
            ],
            "functional_review": {
                "fable": asdict(self.fable) if self.fable else None,
                "snippets": [
                    {
                        "name": s.name,
                        "location": s.location,
                        "signature": s.signature,
                        "has_stub": s.test_stub is not None,
                        "stub_error": s.stub_error,
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
    """Orchestrates discovery -> checks -> functional review -> report."""

    def __init__(
        self,
        target: str,
        *,
        fixtures: Optional[Dict[str, Callable]] = None,
        generate_stubs: bool = True,
        probe: bool = True,
        effort: str = "medium",
        infer_formulas: bool = True,
    ) -> None:
        self.target = target
        self.fixtures = fixtures or {}
        self.generate_stubs = generate_stubs
        self.probe = probe
        self.effort = effort
        self.infer_formulas = infer_formulas

    def run(self) -> Report:
        infos: List[AnnotationInfo] = discover(self.target)
        report = Report()

        for info in infos:
            fixture = self.fixtures.get(info.qualname) or self.fixtures.get(info.name)
            results = _checks.all_checks(info, fixture=fixture)
            report.functions.append(
                FunctionReport(
                    kind=info.kind,
                    name=info.name,
                    qualname=info.qualname,
                    location=info.location,
                    checks=results,
                )
            )

        snippets, status = functional_review(
            infos,
            generate=self.generate_stubs,
            probe=self.probe,
            effort=self.effort,
        )
        report.snippets = snippets
        report.fable = status

        if self.infer_formulas:
            report.formulas = [
                infer_formula(i) for i in infos if i.kind == "functional"
            ]
        return report


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
        lines.append(f"[{_ICON[fr.status]}] @{fr.kind} {fr.name}  ({fr.location})")
        for chk in fr.checks:
            lines.append(f"    - {_ICON[chk.status]} {chk.name}: {chk.message}")
        lines.append("")

    # Functional review section
    if report.snippets:
        lines.append("=" * 70)
        lines.append("@functional review -- inspect these snippets for mathematical correctness:")
        if report.fable:
            state = "available" if report.fable.available else "unavailable"
            lines.append(f"  Fable stub generation: {state} ({report.fable.reason})")
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
            if s.test_stub:
                lines.append("  Generated pytest stub:")
                for stub_line in s.test_stub.splitlines():
                    lines.append(f"    | {stub_line}")
            elif s.stub_error:
                lines.append(f"  (stub not generated: {s.stub_error})")
            lines.append("")

    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2)
