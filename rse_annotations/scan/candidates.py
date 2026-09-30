"""Candidate inference: which annotation an unannotated function most likely deserves."""

from __future__ import annotations

import ast
from typing import Optional, Tuple

from .ast_utils import (_GENERIC_IO, _MATH_SAFE, _called_names, _file_io_calls,
                        _param_names, _returns_a_value)


def _suggest(node: ast.AST) -> Tuple[Optional[str], str, str]:
    """Infer (kind, reason, confidence) for an unannotated function from its body."""
    called = _called_names(node)
    reads, writes = _file_io_calls(node)
    params = _param_names(node)
    returns = _returns_a_value(node)

    if reads and writes:
        return ("data_output",
                f"reads ({', '.join(reads[:3])}) *and* writes ({', '.join(writes[:3])}) "
                f"-- consider splitting into @data_input + @data_output",
                "low")
    if writes:
        specific = [w for w in writes if w not in _GENERIC_IO]
        conf = "high" if specific else "medium"
        hint = "" if specific else " (may be a logger/stream, not a file -- check)"
        return ("data_output",
                f"writes a file/sink: {', '.join(writes[:3])}{hint}", conf)
    if reads:
        specific = [r for r in reads if r not in _GENERIC_IO]
        conf = "high" if specific else "medium"
        hint = "" if specific else " (may be a logger/stream, not a file -- check)"
        return ("data_input",
                f"reads a file/source: {', '.join(reads[:3])}{hint}", conf)

    if not returns:
        return (None, "returns nothing and does no I/O: procedural glue (orchestration/CLI)", "")
    if not params:
        return (None, "returns a value but takes no input and does no I/O: "
                      "constant/config provider", "")

    if "print" in called:
        return ("mapping", "returns a value but also prints; report/format helper", "low")

    impure = sorted(n for n in called if n not in _MATH_SAFE)
    if not impure:
        conf = "high" if not called else "medium"
        detail = "arithmetic only" if not called else f"arithmetic + pure helpers ({', '.join(sorted(called)[:3])})"
        return ("functional", f"pure: {detail}, no I/O, returns a value", conf)

    return ("mapping",
            f"takes input, returns a transformed value, no I/O (calls {', '.join(impure[:3])})",
            "medium")
