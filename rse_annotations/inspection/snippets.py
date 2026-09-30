"""Reviewable code snippets for decorated functions (dependency-free, no LLM).

For any decorator the runner or the interactive inspector can pull the source of
the decorated function so a human can read it. It has no third-party dependencies
and no network use.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Optional

from ..decorators.registry import DecoratorInfo


@dataclass
class Snippet:
    """A reviewable code snippet extracted from a decorated function."""

    name: str
    location: str
    source: str
    signature: str
    docstring: Optional[str] = None


def extract_snippet(info: DecoratorInfo) -> Snippet:
    """Build a :class:`Snippet` from a decorator (pure introspection, no API)."""
    try:
        source = inspect.getsource(info.func)
    except (OSError, TypeError):
        source = f"# source unavailable for {info.qualname}"
    try:
        signature = f"{info.name}{inspect.signature(info.func)}"
    except (TypeError, ValueError):
        signature = info.name
    return Snippet(
        name=info.name,
        location=info.location,
        source=source,
        signature=signature,
        docstring=inspect.getdoc(info.func),
    )
