"""Turn scan records into a text or JSON report."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import List

from ..decorators import CONCERNS
from .scan import Record


def to_json(records: List[Record], errors: List[str]) -> str:
    rows = [{k: v for k, v in asdict(r).items() if k not in ("calls", "source")} for r in records]
    return json.dumps({"functions": rows, "parse_errors": errors}, indent=2)


def to_text(records: List[Record], errors: List[str]) -> str:
    marked = [r for r in records if r.marked]
    pct = 100 * len(marked) / len(records) if records else 0
    out = [f"{len(records)} functions, {len(marked)} marked ({pct:.0f}%)", "",
           f"{'concern':<22}{'marked':>8}{'detected':>10}{'unmarked':>10}"]
    for name in CONCERNS:
        m = sum(name in r.marked for r in records)
        d = sum(name in r.detected for r in records)
        u = sum(name in r.detected and name not in r.marked for r in records)
        out.append(f"{name:<22}{m:>8}{d:>10}{u:>10}")

    missing = [(r, k, f) for r in records for k, f in r.detected.items()
               if f.confidence == "high" and k not in r.marked]
    if missing:
        out += ["", "Detected with high confidence but not marked (all detections: --json):"]
        out += [f"  {r.location}  {r.qualname}  @{k}: {f.reason} [{f.confidence}]"
                for r, k, f in missing]
    unconfirmed = [(r, k) for r in records for k in r.marked if k not in r.detected]
    if unconfirmed:
        out += ["", "Marked but not detected (check the mark or the code):"]
        out += [f"  {r.location}  {r.qualname}  @{k}" for r, k in unconfirmed]
    if errors:
        out += ["", f"{len(errors)} file(s) could not be parsed:"] + [f"  {e}" for e in errors]
    return "\n".join(out)
