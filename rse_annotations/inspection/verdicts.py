"""The human verdicts and the ``inspection.yaml`` file that keeps them.

A hand-rolled reader/writer for our own flat schema, so there is no YAML dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Dict, List, Tuple

VERDICTS = ("accepted", "declined", "pending")
VERDICT_FILE = "inspection.yaml"


@dataclass
class Verdict:
    function: str
    location: str
    concern: str
    formula: str = ""
    verdict: str = "pending"
    note: str = ""

    @property
    def key(self) -> Tuple[str, str, str]:
        return self.function, self.location, self.concern


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s


def dump(verdicts: List[Verdict]) -> str:
    lines = ["# rse_annotations inspection log", f"# verdict: {' | '.join(VERDICTS)}",
             "inspections:"]
    for v in verdicts:
        for i, f in enumerate(fields(Verdict)):
            lines.append(f"{'  - ' if i == 0 else '    '}{f.name}: {_quote(getattr(v, f.name))}")
    return "\n".join(lines) + "\n"


def load(path: Path) -> List[Verdict]:
    if not path.exists():
        return []
    rows: List[Dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s == "inspections:":
            continue
        if s.startswith("- "):
            rows.append({})
            s = s[2:]
        key, _, val = s.partition(":")
        if rows and val:
            rows[-1][key.strip()] = _unquote(val)
    names = {f.name for f in fields(Verdict)}
    return [Verdict(**{k: v for k, v in r.items() if k in names}) for r in rows]
