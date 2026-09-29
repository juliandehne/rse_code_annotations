"""Analyzers over the static AST scan -- they never import or run the target."""

from __future__ import annotations

from typing import List

from ..coverage import CRITICAL_HAZARDS, CoverageReport
from ..findings import AnalysisResult, Finding
from .base import StaticAnalyzer


class CoverageAnalyzer(StaticAnalyzer):
    """How much of the code carries a role annotation, and where the rest should go.

    One ``info`` finding per candidate (an unannotated function whose body looks
    like one of the four kinds), plus a summary finding. ``data`` is the
    :class:`~rse_annotations.coverage.CoverageReport`, so the markdown renderer can
    reproduce the full ``annotation_coverage.md``.
    """

    name = "coverage"
    description = "annotation coverage and candidate functions to annotate"

    def analyze_scan(self, report: CoverageReport) -> AnalysisResult:
        findings: List[Finding] = [Finding(
            "coverage", "info",
            f"{len(report.annotated)}/{len(report.eligible)} eligible functions annotated "
            f"({report.coverage:.0%}) across {report.files_scanned} file(s)",
            evidence={"coverage": report.coverage, "files": report.files_scanned})]
        for rec in report.candidates:
            findings.append(Finding(
                "candidate", "info", f"looks like @{rec.suggested}: {rec.reason}",
                function=f"{rec.module}.{rec.qualname}", location=rec.location,
                evidence={"suggested": rec.suggested, "confidence": rec.confidence}))
        for path, err in report.parse_errors:
            findings.append(Finding("parse_error", "warn", err, location=path))
        return self.result(findings, data=report)


class HazardAnalyzer(StaticAnalyzer):
    """Functions whose behaviour threatens reproducibility or auditability.

    Model calls, human input, external tools, unseeded randomness, statistics,
    unit-of-analysis changes, ... -- see :data:`~rse_annotations.coverage.HAZARDS`.
    Reproducibility-critical hazards are ``warn``, the rest ``info``. Hazards
    inherited through the call graph are marked ``indirect`` in the evidence.
    """

    name = "hazards"
    description = "reproducibility hazards (model calls, randomness, human input, ...)"

    def analyze_scan(self, report: CoverageReport) -> AnalysisResult:
        findings: List[Finding] = []
        for rec in report.hazardous:
            for hz in rec.hazards:
                findings.append(Finding(
                    f"hazard.{hz.kind}",
                    "warn" if hz.kind in CRITICAL_HAZARDS else "info",
                    hz.reason, function=f"{rec.module}.{rec.qualname}", location=rec.location,
                    evidence={"confidence": hz.confidence, "indirect": hz.indirect}))
        return self.result(findings, data=report)
