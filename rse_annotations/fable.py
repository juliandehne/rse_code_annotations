"""Optional Claude Fable 5 integration for @functional correctness review.

For every ``@functional`` function the runner produces a *code snippet* the author
can read to judge mathematical correctness. This module can additionally draft
``pytest`` **stubs** for those snippets using Anthropic's Claude Fable 5 model
(``claude-fable-5``) — but only "if fable is still available".

Availability is probed at runtime (:func:`fable_available`) and the whole feature
degrades gracefully: if the SDK is missing, no key is set, or the probe fails, the
runner falls back to *snippet-only* mode and reports why.

The generated stubs are deliberately scaffolding: they contain ``# TODO`` asserts
and property-test ideas, never fabricated "expected" outputs, so they cannot
silently bless incorrect maths.

Fable-specific API handling (per the claude-api guidance):
  * thinking is always on -> we omit the ``thinking`` parameter;
  * depth via ``output_config={"effort": ...}``;
  * refusal handling + server-side fallback to ``claude-opus-4-8`` enabled by default;
  * no assistant prefill; structured output via ``output_config.format``;
  * requires 30-day data retention (won't run under ZDR).
"""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from typing import List, Optional

from .registry import AnnotationInfo

MODEL = "claude-fable-5"
FALLBACK_MODEL = "claude-opus-4-8"
FALLBACK_BETA = "server-side-fallback-2026-06-01"


@dataclass
class Snippet:
    """A reviewable @functional code snippet plus optional generated test stub."""

    name: str
    location: str
    source: str
    signature: str
    docstring: Optional[str] = None
    test_stub: Optional[str] = None
    stub_error: Optional[str] = None


@dataclass
class FableStatus:
    """Result of the availability probe."""

    available: bool
    reason: str


def extract_snippet(info: AnnotationInfo) -> Snippet:
    """Build a :class:`Snippet` from a ``@functional`` annotation (no API call)."""
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


def fable_available(*, probe: bool = True) -> FableStatus:
    """Check whether Fable can be used right now.

    Order of checks: SDK importable -> API key present -> (optional) probe call.
    """
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return FableStatus(False, "the 'anthropic' SDK is not installed")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return FableStatus(False, "ANTHROPIC_API_KEY is not set")

    if not probe:
        return FableStatus(True, "SDK and key present (probe skipped)")

    try:
        import anthropic

        client = anthropic.Anthropic()
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16,
            messages=[{"role": "user", "content": "ping"}],
            betas=[FALLBACK_BETA],
            fallbacks=[{"model": FALLBACK_MODEL}],
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return FableStatus(False, "probe was refused by safety classifier")
        return FableStatus(True, "probe succeeded")
    except Exception as exc:  # noqa: BLE001
        return FableStatus(False, f"probe failed: {exc!r}")


_STUB_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "test_stub",
        "schema": {
            "type": "object",
            "properties": {
                "pytest_code": {
                    "type": "string",
                    "description": "A pytest module with test function stubs. Use "
                                   "# TODO placeholders for expected values; include "
                                   "property-based test ideas as comments. Never invent "
                                   "concrete expected outputs.",
                },
                "review_notes": {
                    "type": "string",
                    "description": "Short notes on properties worth checking "
                                   "(edge cases, invariants, domains).",
                },
            },
            "required": ["pytest_code", "review_notes"],
            "additionalProperties": False,
        },
    },
}

_PROMPT = """You are helping a research software engineer review a Python function that \
is annotated as a pure mathematical `@functional`. Draft a pytest test module that \
gives the author a scaffold to verify mathematical correctness.

Rules:
- Produce test function stubs named test_<something>.
- Use `# TODO: assert ...` placeholders. DO NOT invent concrete expected outputs — the \
author must supply the ground truth.
- Prefer property-based / invariant checks expressed as comments (e.g. monotonicity, \
identity, bounds, symmetry, inverse relationships) where they apply.
- Include edge cases (zero, negative, empty, large, NaN/inf where relevant) as stubs.

Function under review ({location}):

```python
{source}
```
"""


def generate_stub(snippet: Snippet, *, effort: str = "medium") -> Snippet:
    """Generate a pytest stub for one snippet via Claude Fable 5.

    On any error the snippet's ``stub_error`` is set and ``test_stub`` left ``None``;
    callers should treat stub generation as best-effort.
    """
    try:
        import anthropic

        client = anthropic.Anthropic()
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": _PROMPT.format(location=snippet.location, source=snippet.source),
            }],
            output_config={"effort": effort, "format": _STUB_SCHEMA},
            betas=[FALLBACK_BETA],
            fallbacks=[{"model": FALLBACK_MODEL}],
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            snippet.stub_error = "request refused by safety classifier"
            return snippet

        import json

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        data = json.loads(text)
        header = f"# Auto-generated review stub for {snippet.name} ({snippet.location})\n"
        notes = data.get("review_notes", "").strip()
        note_block = ("\n# Review notes:\n# " + notes.replace("\n", "\n# ") + "\n") if notes else ""
        snippet.test_stub = header + note_block + "\n" + data.get("pytest_code", "")
    except Exception as exc:  # noqa: BLE001
        snippet.stub_error = f"{exc!r}"
    return snippet


def functional_review(
    infos: List[AnnotationInfo],
    *,
    generate: bool = True,
    probe: bool = True,
    effort: str = "medium",
) -> tuple[List[Snippet], FableStatus]:
    """Produce reviewable snippets for all ``@functional`` infos, with optional stubs.

    Returns the snippets and the Fable availability status. If Fable is unavailable
    (or ``generate`` is False) the snippets are returned without ``test_stub``.
    """
    snippets = [extract_snippet(i) for i in infos if i.kind == "functional"]
    status = fable_available(probe=probe) if generate else FableStatus(False, "generation disabled")
    if generate and status.available:
        snippets = [generate_stub(s, effort=effort) for s in snippets]
    return snippets, status
