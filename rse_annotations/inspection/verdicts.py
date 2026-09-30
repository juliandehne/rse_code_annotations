"""Interactive inspection of ``@functional`` annotations.

The point is to help a human *inspect generated code*: for every ``@functional``
we show the source and the inferred formula, then ask the reviewer to accept or
decline it. The verdicts are recorded in an ``inspection.yaml`` next to the code so
the review is auditable and re-runnable (previous verdicts pre-fill the defaults).

To avoid a runtime dependency, this module reads and writes the small, fixed YAML
schema it owns with a hand-rolled emitter/parser -- not a general YAML library.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional
from ..annotations.registry import AnnotationInfo

VERDICTS = ("accepted", "declined", "pending")


@dataclass
class Verdict:
    function: str
    location: str
    kind: str
    formula: str
    verdict: str  # one of VERDICTS
    note: str = ""


# --------------------------------------------------------------------------- #
# Minimal YAML I/O for our own fixed schema (list of flat string records)
# --------------------------------------------------------------------------- #

def _yq(value: str) -> str:
    """Double-quote and escape a scalar string for our YAML subset."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _yunq(raw: str) -> str:
    """Inverse of :func:`_yq` for a possibly-quoted scalar."""
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        body = raw[1:-1]
        return body.replace('\\"', '"').replace("\\\\", "\\")
    return raw


def dump_yaml(verdicts: List[Verdict]) -> str:
    lines = [
        "# rse_code_annotations inspection log",
        "# verdict is one of: accepted | declined | pending",
        "inspections:",
    ]
    if not verdicts:
        lines.append("  []")
        return "\n".join(lines) + "\n"
    for v in verdicts:
        lines.append(f"  - function: {_yq(v.function)}")
        lines.append(f"    location: {_yq(v.location)}")
        lines.append(f"    kind: {_yq(v.kind)}")
        lines.append(f"    formula: {_yq(v.formula)}")
        lines.append(f"    verdict: {_yq(v.verdict)}")
        lines.append(f"    note: {_yq(v.note)}")
    return "\n".join(lines) + "\n"


def load_yaml(path: Path) -> List[Verdict]:
    """Parse an ``inspection.yaml`` we previously wrote. Tolerant of hand-edits."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    verdicts: List[Verdict] = []
    current: Dict[str, str] = {}

    def flush() -> None:
        if current:
            verdicts.append(Verdict(
                function=current.get("function", ""),
                location=current.get("location", ""),
                kind=current.get("kind", ""),
                formula=current.get("formula", ""),
                verdict=current.get("verdict", "pending"),
                note=current.get("note", ""),
            ))

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "inspections:":
            continue
        if stripped.startswith("- "):
            flush()
            current = {}
            stripped = stripped[2:].strip()
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            current[key.strip()] = _yunq(val)
    flush()
    return verdicts


# --------------------------------------------------------------------------- #
# Interactive loop -- kept as a function for existing callers; the logic lives
# in :class:`rse_annotations.inspection.Reviewer`.
# --------------------------------------------------------------------------- #

def run_inspection(
    infos: List[AnnotationInfo],
    out_path,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> List[Verdict]:
    """Walk every ``@functional`` info, prompt accept/decline, write the log.

    Equivalent to ``Reviewer(VerdictStore(out_path), ...).review(infos)``.
    """
    from .review import Reviewer, VerdictStore

    reviewer = Reviewer(VerdictStore(out_path), input_fn=input_fn, output_fn=output_fn)
    return reviewer.review(infos)
