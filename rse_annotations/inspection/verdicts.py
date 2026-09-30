"""The verdicts a human gave, and the ``inspection.yaml`` file that keeps them.

One :class:`Verdict` per reviewed ``@functional``. :class:`VerdictStore` loads and
saves them, so the review is auditable and a re-run pre-fills the previous answers.

To avoid a runtime dependency, this module reads and writes the small, fixed YAML
schema it owns with a hand-rolled emitter/parser -- not a general YAML library.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

VERDICTS = ("accepted", "declined", "pending")

#: The file name, written next to the inspected code.
VERDICT_FILE = "inspection.yaml"


@dataclass
class Verdict:
    function: str
    location: str
    concern: str
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
        lines.append(f"    concern: {_yq(v.concern)}")
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
                concern=current.get("concern", current.get("kind", "")),
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
# The file on disk
# --------------------------------------------------------------------------- #

class VerdictStore:
    """The ``inspection.yaml`` file: load, look up and save :class:`Verdict` records."""

    def __init__(self, path) -> None:
        self.path = Path(path)

    @classmethod
    def for_target(cls, target) -> "VerdictStore":
        return cls(target.output_path(VERDICT_FILE))

    def load(self) -> List[Verdict]:
        return load_yaml(self.path) if self.path.exists() else []

    def by_function(self) -> Dict[Tuple[str, str], Verdict]:
        return {(v.function, v.location): v for v in self.load()}

    def save(self, verdicts: List[Verdict]) -> None:
        self.path.write_text(dump_yaml(verdicts), encoding="utf-8")

