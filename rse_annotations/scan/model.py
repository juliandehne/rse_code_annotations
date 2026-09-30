"""Records produced by the static scan: :class:`FunctionRecord` and :class:`CoverageReport`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..annotations.registry import KINDS
from .hazards import _HAZARD_PRIORITY, HAZARDS, Hazard

#: Candidate kinds, most audit-relevant first (drives the worklist ordering).
_KIND_PRIORITY = {"functional": 0, "data_output": 1, "data_input": 2, "mapping": 3}


@dataclass
class FunctionRecord:
    """One function or method found by the static scan.

    Attributes:
        name: The function's own name.
        qualname: Dotted name within its module, e.g. ``RateLimiter.wait_if_needed``.
        module: Dotted module name derived from the scanned root.
        file: Absolute path to the source file.
        lineno: 1-based line of the ``def``.
        kind: The annotation actually present (one of :data:`~rse_annotations.annotations.registry.KINDS`),
            or ``None`` if the function is unannotated.
        suggested: The annotation this function looks like it deserves, or ``None``
            if it is not a candidate (procedural glue, a dunder, a nested helper).
        reason: Why ``suggested`` was chosen -- or why nothing was.
        confidence: ``"high"``, ``"medium"`` or ``"low"``.
        eligible: False for things an annotation would be meaningless on (dunders,
            nested closures, test helpers). Excluded from the coverage denominator.
        skip_reason: Why ``eligible`` is False.
        class_name: Owning class, if this is a method.
        has_docstring: Whether the function has a docstring (audit signal in itself).
        hazards: Audit hazards found in the body (see :class:`Hazard`). Independent of
            ``kind``/``suggested``: annotated functions can carry hazards too.
        calls: Names this function calls (used to propagate hazards through the tree).
    """

    name: str
    qualname: str
    module: str
    file: str
    lineno: int
    kind: Optional[str] = None
    suggested: Optional[str] = None
    reason: str = ""
    confidence: str = "low"
    eligible: bool = True
    skip_reason: str = ""
    class_name: Optional[str] = None
    has_docstring: bool = False
    hazards: List[Hazard] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)

    @property
    def annotated(self) -> bool:
        return self.kind is not None

    @property
    def is_candidate(self) -> bool:
        """Unannotated, eligible, and we have a concrete kind to propose."""
        return self.eligible and self.kind is None and self.suggested is not None

    @property
    def location(self) -> str:
        return f"{self.file}:{self.lineno}"

    @property
    def hazard_kinds(self) -> List[str]:
        return [h.kind for h in self.hazards]

    def hazard(self, kind: str) -> Optional[Hazard]:
        for h in self.hazards:
            if h.kind == kind:
                return h
        return None


@dataclass
class CoverageReport:
    """The result of a static scan of a research-software tree."""

    root: Path
    records: List[FunctionRecord] = field(default_factory=list)
    files_scanned: int = 0
    parse_errors: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def eligible(self) -> List[FunctionRecord]:
        return [r for r in self.records if r.eligible]

    @property
    def annotated(self) -> List[FunctionRecord]:
        return [r for r in self.records if r.annotated]

    @property
    def candidates(self) -> List[FunctionRecord]:
        """Unannotated functions worth annotating, most audit-relevant first."""
        cands = [r for r in self.records if r.is_candidate]
        return sorted(cands, key=lambda r: (_KIND_PRIORITY.get(r.suggested, 9),
                                            r.file, r.lineno))

    @property
    def coverage(self) -> float:
        """Fraction of *eligible* functions that carry an annotation (0.0--1.0)."""
        n = len(self.eligible)
        return (len(self.annotated) / n) if n else 0.0

    @property
    def hazardous(self) -> List[FunctionRecord]:
        """Eligible functions carrying at least one audit hazard, worst first."""
        hits = [r for r in self.eligible if r.hazards]
        return sorted(hits, key=lambda r: (min(_HAZARD_PRIORITY[h.kind] for h in r.hazards),
                                           r.file, r.lineno))

    def counts_by_kind(self) -> Dict[str, int]:
        return {k: sum(1 for r in self.records if r.kind == k) for k in KINDS}

    def suggested_by_kind(self) -> Dict[str, int]:
        return {k: sum(1 for r in self.candidates if r.suggested == k) for k in KINDS}

    def counts_by_hazard(self) -> Dict[str, int]:
        return {h: sum(1 for r in self.eligible if r.hazard(h)) for h in HAZARDS}

    @property
    def hazard_rate(self) -> float:
        """Fraction of *eligible* functions that are a hazard rather than plumbing."""
        n = len(self.eligible)
        return (len(self.hazardous) / n) if n else 0.0

    def by_file(self) -> Dict[str, List[FunctionRecord]]:
        out: Dict[str, List[FunctionRecord]] = {}
        for r in self.records:
            out.setdefault(r.file, []).append(r)
        return out
