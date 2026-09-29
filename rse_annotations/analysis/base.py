"""The analyzer base classes -- also the plugin contract.

Every check the tool can run over a :class:`~rse_annotations.target.TargetProject` is
a subclass of :class:`Analyzer`. Built-ins and third-party plugins are the same kind
of object; a plugin package only has to subclass one of these and advertise the
class under the ``rse_annotations.analyzers`` entry-point group (see
:mod:`rse_annotations.analysis.plugins`).

Two intermediate bases cover the two ways of looking at research code:

* :class:`AnnotationAnalyzer` -- works on the annotated functions, which requires
  *importing* the target; subclasses implement :meth:`~AnnotationAnalyzer.analyze_function`.
* :class:`StaticAnalyzer` -- works on the AST scan, which never imports or runs the
  target; subclasses implement :meth:`~StaticAnalyzer.analyze_scan`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, List, Tuple

from ..findings import AnalysisResult, Finding
from ..registry import KINDS, AnnotationInfo

#: When an analyzer runs: over source only, while tests run, while the target runs,
#: or as a gate in continuous integration.
PHASES = ("static", "test", "runtime", "ci")


class Analyzer(ABC):
    """One pluggable check over a target project.

    Class attributes a subclass sets:
        name: Unique short identifier, used on the command line (``--only math``).
        description: One line for ``--list-analyzers``.
        when: One of :data:`PHASES`.
        imports_target: True if running it imports (and so executes) the target code.
    """

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    when: ClassVar[str] = "static"
    imports_target: ClassVar[bool] = False

    def available(self) -> bool:
        """False if an optional dependency is missing; the analyzer is then skipped."""
        return True

    @abstractmethod
    def analyze(self, target) -> AnalysisResult:
        """Examine ``target`` (a :class:`~rse_annotations.target.TargetProject`)."""

    # helpers for subclasses
    def result(self, findings=None, *, data=None, skipped=None) -> AnalysisResult:
        return AnalysisResult(self.name, list(findings or []), data=data, skipped=skipped)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name!r} ({self.when})>"


class AnnotationAnalyzer(Analyzer):
    """Base for analyzers that inspect the annotated functions one by one.

    Subclasses set :attr:`kinds` to the annotation kinds they care about and
    implement :meth:`analyze_function`. :meth:`collect` may be overridden to build
    a native result object (``data``) from the whole batch.
    """

    kinds: ClassVar[Tuple[str, ...]] = KINDS
    imports_target: ClassVar[bool] = True

    def select(self, target) -> List[AnnotationInfo]:
        return [i for i in target.annotations() if i.kind in self.kinds]

    def analyze(self, target) -> AnalysisResult:
        infos = self.select(target)
        if not infos:
            wanted = ", ".join(f"@{k}" for k in self.kinds)
            return self.result(skipped=f"no {wanted} annotations in {target.name}")
        findings: List[Finding] = []
        for info in infos:
            findings.extend(self.analyze_function(info))
        return self.result(findings, data=self.collect(infos))

    @abstractmethod
    def analyze_function(self, info: AnnotationInfo) -> List[Finding]:
        """Findings for one annotated function."""

    def collect(self, infos: List[AnnotationInfo]):
        return None


class StaticAnalyzer(Analyzer):
    """Base for analyzers that read the AST scan and never import the target."""

    imports_target: ClassVar[bool] = False

    def analyze(self, target) -> AnalysisResult:
        return self.analyze_scan(target.static_scan())

    @abstractmethod
    def analyze_scan(self, report) -> AnalysisResult:
        """Findings from a :class:`~rse_annotations.coverage.CoverageReport`."""
