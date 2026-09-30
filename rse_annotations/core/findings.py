"""The common currency of every plugin: :class:`Finding` and :class:`AnalysisResult`.

Built-in and third-party plugins report in the same shape, so renderers,
the CLI and CI gates never need to know which plugin produced a finding. The
plugin-specific payload (a :class:`~rse_annotations.scan.CoverageReport`, a
list of formulas, ...) travels alongside in :attr:`AnalysisResult.data`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

#: Ordered from harmless to blocking.
SEVERITIES = ("info", "warn", "fail")


@dataclass
class Finding:
    """One observation about the target.

    Attributes:
        rule: Short identifier of what was checked, e.g. ``"placement"``, ``"hazard.stochastic"``.
        severity: One of :data:`SEVERITIES`.
        message: Human-readable explanation.
        function: Qualified name of the function concerned, if any.
        location: ``file:line`` of the evidence, if any.
        evidence: Free-form machine-readable detail (for ``rse_evidence.json``).
    """

    rule: str
    severity: str
    message: str
    function: Optional[str] = None
    location: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}, got {self.severity!r}")


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
    def status(self) -> str:
        """``skipped``, ``fail``, ``warn`` or ``pass`` (worst finding wins)."""
        if self.skipped:
            return "skipped"
        severities = {f.severity for f in self.findings}
        if "fail" in severities:
            return "fail"
        if "warn" in severities:
            return "warn"
        return "pass"

    @property
    def ok(self) -> bool:
        return self.status != "fail"

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    def to_dict(self) -> dict:
        return {
            "plugin": self.plugin,
            "status": self.status,
            "skipped": self.skipped,
            "findings": [asdict(f) for f in self.findings],
        }
