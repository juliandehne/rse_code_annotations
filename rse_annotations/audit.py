"""The front door: one :class:`Audit` of one :class:`~rse_annotations.target.TargetProject`.

::

    from rse_annotations import Audit, TargetProject, TextRenderer

    audit = Audit(TargetProject.parse("https://github.com/org/repo"))
    report = audit.run(only=["coverage", "hazards"])
    print(TextRenderer().render_results(report.results))

    audit.test_generator().write()        # pytest scaffolds
    audit.reviewer().review(audit.target.annotations())   # human verdicts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .analysis.base import Analyzer
from .analysis.plugins import AnalyzerCatalog, default_catalog
from .findings import AnalysisResult, Finding
from .review import Reviewer, VerdictStore
from .testing import TestGenerator


@dataclass
class AuditReport:
    """The results of every analyzer that took part in one :meth:`Audit.run`."""

    target: str
    results: List[AnalysisResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    def result(self, analyzer: str) -> AnalysisResult:
        for r in self.results:
            if r.analyzer == analyzer:
                return r
        raise KeyError(analyzer)

    def to_dict(self) -> dict:
        return {"target": self.target, "ok": self.ok,
                "results": [r.to_dict() for r in self.results]}


class Audit:
    """Runs analyzers over a target and hands out the reviewer and test generator.

    Args:
        target: The project under audit.
        catalog: Where analyzers come from; defaults to built-ins + stubs + plugins.
        analyzers: Explicit analyzer instances (e.g. configured ones); overrides
            ``catalog`` selection in :meth:`run`.
    """

    def __init__(self, target, *, catalog: Optional[AnalyzerCatalog] = None,
                 analyzers: Optional[List[Analyzer]] = None) -> None:
        self.target = target
        self.catalog = catalog if catalog is not None else default_catalog()
        self.analyzers = analyzers

    def select(self, only: Optional[Iterable[str]] = None,
               when: Optional[Iterable[str]] = None) -> List[Analyzer]:
        if self.analyzers is not None:
            chosen = self.analyzers
            if only:
                wanted = set(only)
                chosen = [a for a in chosen if a.name in wanted]
            if when is not None:
                phases = set(when)
                chosen = [a for a in chosen if a.when in phases]
            return list(chosen)
        return self.catalog.create(only, when=when)

    def run(self, only: Optional[Iterable[str]] = None,
            when: Optional[Iterable[str]] = None) -> AuditReport:
        """Run the selected analyzers. Unavailable ones are reported as skipped;
        an analyzer that crashes yields one ``fail`` finding instead of aborting."""
        report = AuditReport(self.target.name)
        for analyzer in self.select(only, when):
            report.results.append(self.run_one(analyzer))
        return report

    def run_one(self, analyzer: Analyzer) -> AnalysisResult:
        if not analyzer.available():
            return analyzer.result(skipped=analyzer.unavailable_reason())
        try:
            return analyzer.analyze(self.target)
        except Exception as exc:  # noqa: BLE001 - one broken analyzer must not stop the audit
            return analyzer.result([Finding("analyzer_error", "fail",
                                            f"{type(exc).__name__}: {exc}")])

    def reviewer(self, **io) -> Reviewer:
        return Reviewer(VerdictStore.for_target(self.target), **io)

    def test_generator(self, out_dir=None) -> TestGenerator:
        return TestGenerator(self.target, out_dir)
