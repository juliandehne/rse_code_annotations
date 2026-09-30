"""Candidate inference: which decorator an undecorated function most likely deserves."""

from __future__ import annotations

import ast
from typing import Optional, Tuple

from . import vocabulary as vocab
from .ast_utils import (_called_names, _file_io_calls,
                        _param_names, _returns_a_value)
from ..decorators.markers import HazardDecorator


def _suggest(node: ast.AST) -> Tuple[Optional[str], str, str]:
    """Infer (kind, reason, confidence) for an undecorated function from its body."""
    called = _called_names(node)
    reads, writes = _file_io_calls(node)
    params = _param_names(node)
    returns = _returns_a_value(node)

    if reads and writes:
        return (HazardDecorator.DATA_OUTPUT,
                f"reads ({', '.join(reads[:3])}) *and* writes ({', '.join(writes[:3])}) "
                f"-- consider splitting into @data_input + @data_output",
                "low")
    if writes:
        specific = [w for w in writes if w not in vocab.GENERIC_IO]
        conf = "high" if specific else "medium"
        hint = "" if specific else " (may be a logger/stream, not a file -- check)"
        return (HazardDecorator.DATA_OUTPUT,
                f"writes a file/sink: {', '.join(writes[:3])}{hint}", conf)
    if reads:
        specific = [r for r in reads if r not in vocab.GENERIC_IO]
        conf = "high" if specific else "medium"
        hint = "" if specific else " (may be a logger/stream, not a file -- check)"
        return (HazardDecorator.DATA_INPUT,
                f"reads a file/source: {', '.join(reads[:3])}{hint}", conf)

    if not returns:
        return (None, "returns nothing and does no I/O: procedural glue (orchestration/CLI)", "")
    if not params:
        return (None, "returns a value but takes no input and does no I/O: "
                      "constant/config provider", "")

    if "print" in called:
        return (HazardDecorator.MAPPING, "returns a value but also prints; report/format helper", "low")

    impure = sorted(n for n in called if n not in vocab.MATH_SAFE)
    if not impure:
        conf = "high" if not called else "medium"
        detail = "arithmetic only" if not called else f"arithmetic + pure helpers ({', '.join(sorted(called)[:3])})"
        return (HazardDecorator.FUNCTIONAL, f"pure: {detail}, no I/O, returns a value", conf)

    return (HazardDecorator.MAPPING,
            f"takes input, returns a transformed value, no I/O (calls {', '.join(impure[:3])})",
            "medium")
