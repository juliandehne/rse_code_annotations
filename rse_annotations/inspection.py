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

from .formula import infer_formula
from .registry import AnnotationInfo
from .snippets import extract_snippet

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
# Interactive loop
# --------------------------------------------------------------------------- #

def _formula_line(info: AnnotationInfo) -> str:
    res = infer_formula(info)
    if res.ast_forms:
        return res.ast_forms[0]
    if res.sympy_form:
        return res.sympy_form
    return "(no closed-form formula could be inferred; inspect the source)"


def run_inspection(
    infos: List[AnnotationInfo],
    out_path,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> List[Verdict]:
    """Walk every ``@functional`` info, prompt accept/decline, write the log.

    Args:
        infos: annotations to inspect (non-functional ones are ignored).
        out_path: where to write ``inspection.yaml``.
        input_fn/output_fn: injectable I/O for testing (default stdin/stdout).

    Returns:
        The list of :class:`Verdict` recorded (also written to ``out_path``).
    """
    out_path = Path(out_path)
    functional = [i for i in infos if i.kind == "functional"]

    previous = {(v.function, v.location): v for v in load_yaml(out_path)}

    if not functional:
        output_fn("No @functional annotations found to inspect.")
        dump = dump_yaml([])
        out_path.write_text(dump, encoding="utf-8")
        return []

    verdicts: List[Verdict] = []
    total = len(functional)
    for idx, info in enumerate(functional, start=1):
        snippet = extract_snippet(info)
        formula = _formula_line(info)
        prior = previous.get((info.name, info.location))

        output_fn("")
        output_fn(f"[{idx}/{total}] {info.name}   ({info.location})")
        output_fn(f"formula: {formula}")
        if prior and prior.verdict in VERDICTS:
            output_fn(f"(previously: {prior.verdict})")
        output_fn("--- source ---")
        for src_line in snippet.source.splitlines():
            output_fn(f"    {src_line}")

        default = prior.verdict if prior else "pending"
        verdict = _ask(input_fn, output_fn, default)
        verdicts.append(Verdict(
            function=info.name,
            location=info.location,
            kind=info.kind,
            formula=formula,
            verdict=verdict,
        ))

    out_path.write_text(dump_yaml(verdicts), encoding="utf-8")
    accepted = sum(1 for v in verdicts if v.verdict == "accepted")
    declined = sum(1 for v in verdicts if v.verdict == "declined")
    pending = sum(1 for v in verdicts if v.verdict == "pending")
    output_fn("")
    output_fn(f"Recorded {len(verdicts)} verdict(s): "
              f"{accepted} accepted, {declined} declined, {pending} pending.")
    output_fn(f"Written to {out_path}")
    return verdicts


def _ask(input_fn, output_fn, default: str) -> str:
    """Prompt for a single accept/decline/skip verdict; returns a VERDICTS value."""
    prompt = "Accept this @functional as correct? [y]es / [n]o / [s]kip > "
    while True:
        try:
            answer = input_fn(prompt).strip().lower()
        except EOFError:
            return default  # non-interactive / stream exhausted -> keep default
        if answer == "":
            return default
        if answer in ("y", "yes"):
            return "accepted"
        if answer in ("n", "no"):
            return "declined"
        if answer in ("s", "skip"):
            return "pending"
        output_fn("  please answer y, n, or s")
