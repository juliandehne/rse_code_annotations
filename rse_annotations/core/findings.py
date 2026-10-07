"""The common currency of every plugin: :class:`Finding` and :class:`AnalysisResult`.

Built-in and third-party plugins report in the same shape, so renderers,
the CLI and CI gates never need to know which plugin produced a finding. The
plugin-specific payload (a :class:`~rse_annotations.scan.CoverageReport`, a
list of formulas, ...) travels alongside in :attr:`AnalysisResult.data`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from ..textenum import TextEnum


class Severity(TextEnum):
    """How bad one :class:`Finding` is, ordered from harmless to blocking."""

    INFO = "info"
    WARN = "warn"
    FAIL = "fail"


class Status(TextEnum):
    """The outcome of one plugin (:attr:`AnalysisResult.status`) or one check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIPPED = "skipped"

    @property
    def mark(self) -> str:
        """The four-letter mark shown in text reports, e.g. ``"PASS"``."""
        return STATUS_MARKS[self]


#: Every :class:`Severity`, ordered from harmless to blocking.
SEVERITIES = tuple(Severity)

#: How a :class:`Status` is shown in text reports.
STATUS_MARKS = {Status.PASS: "PASS", Status.WARN: "WARN", Status.FAIL: "FAIL",
                Status.SKIPPED: "SKIP"}


@dataclass
class Finding:
    """One observation about the target.

    Attributes:
        rule: Short identifier of what was checked, e.g. ``"placement"``, ``"hazard.stochastic"``.
        severity: A :class:`Severity` (the plain string, e.g. ``"warn"``, is accepted too).
        message: Human-readable explanation.
        function: Qualified name of the function concerned, if any.
        location: ``file:line`` of the evidence, if any.
        evidence: Free-form machine-readable detail (for ``rse_evidence.json``).
    """

    rule: str
    severity: Severity
    message: str
    function: Optional[str] = None
    location: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {', '.join(SEVERITIES)}, "
                             f"got {self.severity!r}")
        self.severity = Severity(self.severity)


@dataclass
class AnalysisResult:
    """Everything one plugin reported about one target.

    Attributes:
        plugin: The plugin's :attr:`~rse_annotations.core.plugin.Plugin.name`.
        findings: The observations, in the plugin's order.
        data: The plugin's native result object, for renderers that know it.
        skipped: Why the plugin did not run (missing extra, nothing to analyse).
    """

    plugin: str
    findings: List[Finding] = field(default_factory=list)
    data: Any = None
    skipped: Optional[str] = None

    @property
    def status(self) -> Status:
        """``skipped``, ``fail``, ``warn`` or ``pass`` (worst finding wins)."""
        if self.skipped:
            return Status.SKIPPED
        severities = {f.severity for f in self.findings}
        if Severity.FAIL in severities:
            return Status.FAIL
        if Severity.WARN in severities:
            return Status.WARN
        return Status.PASS

    @property
    def ok(self) -> bool:
        return self.status != Status.FAIL

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    def to_dict(self) -> dict:
        return {
            "plugin": self.plugin,
            "status": self.status,
            "skipped": self.skipped,
            "findings": [asdict(f) for f in self.findings],
        }
