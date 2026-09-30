"""Records produced by the static scan: :class:`FunctionRecord` and :class:`CoverageReport`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..decorators.markers import REVIEW_CONCERNS, HazardDecorator
from .hazards import _HAZARD_PRIORITY, HAZARDS, Hazard

#: Candidate kinds, most audit-relevant first (drives the worklist ordering).
_KIND_PRIORITY = {HazardDecorator.FUNCTIONAL: 0, HazardDecorator.DATA_OUTPUT: 1, HazardDecorator.DATA_INPUT: 2, HazardDecorator.MAPPING: 3}


@dataclass
class FunctionRecord:
    """One function or method found by the static scan.

    Attributes:
        name: The function's own name.
        qualname: Dotted name within its module, e.g. ``RateLimiter.wait_if_needed``.
        module: Dotted module name derived from the scanned root.
        file: Absolute path to the source file.
        lineno: 1-based line of the ``def``.
        concern: The decorator actually present (one of :data:`~rse_annotations.decorators.registry.REVIEW_CONCERNS`),
            or ``None`` if the function is undecorated.
        suggested: The decorator this function looks like it deserves, or ``None``
            if it is not a candidate (procedural glue, a dunder, a nested helper).
        reason: Why ``suggested`` was chosen -- or why nothing was.
        confidence: ``"high"``, ``"medium"`` or ``"low"``.
        eligible: False for things a decorator would be meaningless on (dunders,
            nested closures, test helpers). Excluded from the coverage denominator.
        skip_reason: Why ``eligible`` is False.
        class_name: Owning class, if this is a method.
        has_docstring: Whether the function has a docstring (audit signal in itself).
        hazards: Audit hazards found in the body (see :class:`Hazard`). Independent of
            ``concern``/``suggested``: decorated functions can carry hazards too.
        calls: Names this function calls (used to propagate hazards through the tree).
    """

    name: str
    qualname: str
    module: str
    file: str
    lineno: int
    concern: Optional[str] = None
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
    def decorated(self) -> bool:
        return self.concern is not None

    @property
    def is_candidate(self) -> bool:
        """Undecorated, eligible, and we have a concrete concern to propose."""
        return self.eligible and self.concern is None and self.suggested is not None

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
    def decorated(self) -> List[FunctionRecord]:
        return [r for r in self.records if r.decorated]

    @property
    def candidates(self) -> List[FunctionRecord]:
        """Undecorated functions worth annotating, most audit-relevant first."""
        cands = [r for r in self.records if r.is_candidate]
        return sorted(cands, key=lambda r: (_KIND_PRIORITY.get(r.suggested, 9),
                                            r.file, r.lineno))

    @property
    def coverage(self) -> float:
        """Fraction of *eligible* functions that carry a decorator (0.0--1.0)."""
        n = len(self.eligible)
        return (len(self.decorated) / n) if n else 0.0

    @property
    def hazardous(self) -> List[FunctionRecord]:
        """Eligible functions carrying at least one audit hazard, worst first."""
        hits = [r for r in self.eligible if r.hazards]
        return sorted(hits, key=lambda r: (min(_HAZARD_PRIORITY[h.kind] for h in r.hazards),
                                           r.file, r.lineno))

    def counts_by_kind(self) -> Dict[str, int]:
        return {k: sum(1 for r in self.records if r.concern == k) for k in REVIEW_CONCERNS}

    def suggested_by_kind(self) -> Dict[str, int]:
        return {k: sum(1 for r in self.candidates if r.suggested == k) for k in REVIEW_CONCERNS}

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
