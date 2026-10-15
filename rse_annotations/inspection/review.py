"""Interactive review of marked functions: one y/n/s answer per (function, concern).

Static like the analysis: the target is parsed, never imported. Answers go to
``inspection.yaml`` next to the scanned code, so a re-run pre-fills them.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, Dict, Optional

from ..analysis import scan
from ..decorators import Concern
from . import verdicts as vs

ANSWERS = {"y": "accepted", "yes": "accepted", "n": "declined", "no": "declined",
           "s": "pending", "skip": "pending"}


def formula(source: str) -> str:
    """``f(...) = <expr>`` when the body is a single return statement, else ``""``."""
    try:
        fn = ast.parse(source).body[0]
    except (SyntaxError, IndexError):
        return ""
    body = [n for n in fn.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    if len(body) == 1 and isinstance(body[0], ast.Return) and body[0].value is not None:
        return f"{fn.name}(...) = {ast.unparse(body[0].value)}"
    return ""


def review(root, concerns: Dict[str, Concern], concern: Optional[str] = None,
           input_fn: Callable[[str], str] = input,
           output_fn: Callable[[str], None] = print) -> list:
    """Walk every marked function (optionally only ``concern``) and record a verdict each."""
    root = Path(root).resolve()
    store = (root.parent if root.is_file() else root) / vs.VERDICT_FILE
    old = {v.key: v for v in vs.load(store)}
    records, _ = scan(root, concerns)
    todo = [(r, k) for r in records for k in r.marked if concern in (None, k)]
    results = []
    for i, (rec, k) in enumerate(todo, 1):
        v = vs.Verdict(rec.qualname, rec.location, k, formula(rec.source) if k == "calculations" else "")
        if (prev := old.get(v.key)):
            v.verdict, v.note = prev.verdict, prev.note
        output_fn(f"\n[{i}/{len(todo)}] @{k}  {rec.qualname}  ({rec.location})")
        output_fn(rec.source)
        if v.formula:
            output_fn(f"  formula: {v.formula}")
        output_fn(f'  Does the assertion "{concerns[k].assertion.rstrip(".")}" hold?')
        v.verdict = _ask(f"  [y]es / [n]o / [s]kip (default {v.verdict}): ", v.verdict, input_fn, output_fn)
        results.append(v)
        kept = [o for o in old.values() if o.key not in {r.key for r in results}]
        store.write_text(vs.dump(results + kept), encoding="utf-8")
    counts = ", ".join(f"{sum(r.verdict == d for r in results)} {d}" for d in vs.VERDICTS)
    output_fn(f"\n{len(results)} reviewed: {counts}. Saved to {store}" if results
              else "\nNo marked functions to review.")
    return results


def _ask(prompt, default, input_fn, output_fn) -> str:
    while True:
        try:
            answer = input_fn(prompt).strip().lower()
        except EOFError:
            return default
        if not answer:
            return default
        if answer in ANSWERS:
            return ANSWERS[answer]
        output_fn("  please answer y, n, or s")
