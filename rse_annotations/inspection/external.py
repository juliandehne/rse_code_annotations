"""External review: an outside reviewer inspects the marked snippets and signs a protocol.

Human inspection (:mod:`.review`) is the *author* checking their own code. The
external review is somebody else in the reviewer role -- a journal editor, a peer
reviewer, a person reproducing the result. In both, the marks are a **filter**: they cut
the code a human has to read down to the snippets the claim and its reproducibility rest
on. A decorator is the author saying "look here, for this concern";
:class:`ExternalReviewer` steps the reviewer through every such mark, concern by
concern, instead of the whole repository. For each snippet it shows the question to
answer (the decorator's docstring), the author's notes (``fields=``), the author's own
verdict, the hazards the scan found in the body and the source itself, then asks for a
verdict and a note. The answers are written to ``review_protocol.yaml``
(:class:`ProtocolStore`), next to -- never over -- the authors' ``inspection.yaml``.

The review is **static**: the files are parsed, never imported. The reviewer needs
neither the authors' dependencies nor their hardware to read what
``@hardware_dependency`` points at.
"""

from __future__ import annotations

import ast
import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from ..decorators.markers import CONCERN_HELP, REVIEW_CONCERNS
from ..scan import CoverageReport, FunctionRecord
from .verdicts import (VERDICTS, Decision, Verdict, VerdictStore, _yq, _yunq, ask_verdict,
                       count_verdicts, same_file, verdict_summary)

#: The file the protocol is written to, next to the code.
PROTOCOL_FILE = "review_protocol.yaml"


# --------------------------------------------------------------------------- #
# What the reviewer is shown
# --------------------------------------------------------------------------- #

@dataclass
class ReviewItem:
    """One marked snippet the reviewer should read.

    Attributes:
        record: The function as the static scan saw it (name, location, hazards).
        location: ``file:line``, relative to the reviewed root.
        source: The snippet, decorators included.
        notes: The author's ``fields=`` on the decorator (name -> description).
        author_verdict: The author's own verdict from ``inspection.yaml``, if recorded.
    """

    record: FunctionRecord
    location: str
    source: str
    notes: Dict[str, str] = field(default_factory=dict)
    author_verdict: Optional[str] = None


def _read_snippet(rec: FunctionRecord) -> tuple:
    """``(source, notes)`` of ``rec``, read from its file without importing it."""
    try:
        text = Path(rec.file).read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return f"# source unavailable for {rec.qualname}", {}
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == rec.name and node.lineno == rec.lineno):
            first = min([d.lineno for d in node.decorator_list] + [node.lineno])
            source = "\n".join(text.splitlines()[first - 1:node.end_lineno])
            return source, _declared_fields(node)
    return f"# source unavailable for {rec.qualname}", {}


def _declared_fields(node: ast.AST) -> Dict[str, str]:
    """The literal ``fields={...}`` of a decorator call such as ``@data_input(fields=...)``."""
    for dec in node.decorator_list:
        for kw in getattr(dec, "keywords", []):
            if kw.arg == "fields":
                try:
                    value = ast.literal_eval(kw.value)
                except ValueError:
                    return {}
                return {str(k): str(v) for k, v in value.items()} if isinstance(value, dict) else {}
    return {}


def _verdict_of(rec: FunctionRecord, verdicts: List[Verdict]) -> Optional[str]:
    for v in verdicts:
        if v.function == rec.name and same_file(v.location.rsplit(":", 1)[0], rec.file):
            return v.verdict
    return None


def question(concern: str) -> str:
    """What to review for ``concern``: the last paragraph of the decorator's docstring."""
    return " ".join((CONCERN_HELP[concern] or "").split("\n\n")[-1].split())


def review_items(target) -> Tuple[CoverageReport, List[ReviewItem]]:
    """The static scan of ``target`` and its marked snippets, ordered concern by concern."""
    report = target.static_scan()
    verdicts = VerdictStore.for_target(target).load()
    root = Path(report.root).resolve()
    items: List[ReviewItem] = []
    for rec in sorted(report.decorated, key=lambda r: (r.file, r.lineno)):
        try:
            path = Path(rec.file).resolve().relative_to(root)
        except ValueError:
            path = Path(rec.file)
        source, notes = _read_snippet(rec)
        items.append(ReviewItem(rec, f"{path.as_posix()}:{rec.lineno}", source, notes,
                                _verdict_of(rec, verdicts)))
    order = {c: i for i, c in enumerate(REVIEW_CONCERNS)}
    items.sort(key=lambda it: order.get(it.record.concern, len(order)))
    return report, items


# --------------------------------------------------------------------------- #
# The protocol on disk
# --------------------------------------------------------------------------- #

@dataclass
class ReviewFinding:
    """The reviewer's answer for one snippet."""

    function: str
    location: str
    concern: str
    question: str
    verdict: Decision
    note: str = ""


@dataclass
class Protocol:
    """One external review: who looked at what, when, and what they found.

    Attributes:
        target: Name of the reviewed project.
        reviewer: Who reviewed (name or role), as they stated it.
        date: ISO date of the (last) session.
        scope: How much of the code the review covered, e.g. ``8 of 10 eligible
            function(s) marked``. What is not marked was not reviewed.
        findings: One :class:`ReviewFinding` per marked snippet.
    """

    target: str = ""
    reviewer: str = ""
    date: str = ""
    scope: str = ""
    findings: List[ReviewFinding] = field(default_factory=list)

    def counts(self) -> Dict[Decision, int]:
        return count_verdicts(self.findings)


_HEADER_KEYS = ("target", "reviewer", "date", "scope")
_FINDING_KEYS = ("function", "location", "concern", "question", "verdict", "note")


def dump_protocol(protocol: Protocol) -> str:
    lines = [
        "# rse_code_annotations review protocol (external review)",
        "# verdict is one of: accepted | declined | pending",
    ]
    lines += [f"{k}: {_yq(getattr(protocol, k))}" for k in _HEADER_KEYS]
    lines.append("findings:")
    if not protocol.findings:
        lines.append("  []")
    for f in protocol.findings:
        for i, k in enumerate(_FINDING_KEYS):
            lines.append(f"  {'-' if i == 0 else ' '} {k}: {_yq(getattr(f, k))}")
    return "\n".join(lines) + "\n"


def load_protocol(path: Path) -> Protocol:
    """Parse a ``review_protocol.yaml`` we previously wrote. Tolerant of hand-edits."""
    protocol = Protocol()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return protocol
    current: Optional[Dict[str, str]] = None

    def flush() -> None:
        if current:
            protocol.findings.append(ReviewFinding(
                **{k: current.get(k, "") for k in _FINDING_KEYS if k != "verdict"},
                verdict=current.get("verdict", Decision.PENDING)))

    in_findings = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "[]":
            continue
        if stripped == "findings:":
            in_findings = True
            continue
        if stripped.startswith("- "):
            flush()
            current = {}
            stripped = stripped[2:].strip()
        key, sep, val = stripped.partition(":")
        if not sep:
            continue
        if in_findings and current is not None:
            current[key.strip()] = _yunq(val)
        elif key.strip() in _HEADER_KEYS:
            setattr(protocol, key.strip(), _yunq(val))
    flush()
    return protocol


class ProtocolStore:
    """The ``review_protocol.yaml`` file: load and save a :class:`Protocol`."""

    def __init__(self, path) -> None:
        self.path = Path(path)

    @classmethod
    def for_target(cls, target) -> "ProtocolStore":
        return cls(target.output_path(PROTOCOL_FILE))

    def load(self) -> Protocol:
        return load_protocol(self.path) if self.path.exists() else Protocol()

    def save(self, protocol: Protocol) -> None:
        self.path.write_text(dump_protocol(protocol), encoding="utf-8")


# --------------------------------------------------------------------------- #
# The interactive loop
# --------------------------------------------------------------------------- #

class ExternalReviewer:
    """Steps an outside reviewer through every marked snippet and records a protocol.

    Args:
        store: Where the protocol is read from and written to.
        input_fn / output_fn: Injectable I/O (tests pass lists; the CLI passes
            ``input`` / ``print``).
    """

    reviewer_prompt = "Reviewer (name or role){default} > "
    verdict_prompt = "Does this snippet hold up for @{concern}? [y]es / [n]o / [s]kip > "
    note_prompt = "Note for the protocol (Enter for none) > "

    def __init__(self, store: ProtocolStore, *,
                 input_fn: Callable[[str], str] = input,
                 output_fn: Callable[[str], None] = print) -> None:
        self.store = store
        self.input_fn = input_fn
        self.output_fn = output_fn

    def review(self, target) -> Protocol:
        """Review every marked snippet of ``target``; write and return the protocol."""
        out = self.output_fn
        report, items = review_items(target)
        previous = self.store.load()
        prior = {(f.function, f.concern, f.location.rsplit(":", 1)[0]): f
                 for f in previous.findings}

        protocol = Protocol(
            target=target.name, date=datetime.date.today().isoformat(),
            scope=f"{len(report.decorated)} of {len(report.eligible)} eligible "
                  f"function(s) marked ({report.coverage:.0%}); unmarked code was not reviewed")
        out("")
        out(f"External review of {report.root}")
        out(f"  {len(items)} marked snippet(s); nothing is imported or run.")
        if not items:
            out("No decorators found to review.")
        else:
            protocol.reviewer = self.ask_text(
                self.reviewer_prompt.format(
                    default=f" [{previous.reviewer}]" if previous.reviewer else ""),
                previous.reviewer)

        concern = None
        for idx, item in enumerate(items, start=1):
            rec = item.record
            if rec.concern != concern:
                concern = rec.concern
                out("")
                out(f"== @{concern} -- {question(concern)}")
            before = prior.get((rec.qualname, str(rec.concern), item.location.rsplit(":", 1)[0]))
            self.present(item, before, idx, len(items))
            verdict = self.ask_verdict(rec.concern, before.verdict if before else Decision.PENDING)
            note = self.ask_text(self.note_prompt, before.note if before else "")
            protocol.findings.append(ReviewFinding(
                function=rec.qualname, location=item.location, concern=str(rec.concern),
                question=question(rec.concern), verdict=verdict, note=note))

        self.store.save(protocol)
        out("")
        out(f"Recorded {len(protocol.findings)} finding(s): {verdict_summary(protocol.findings)}")
        out(f"Scope: {protocol.scope}.")
        out(f"Protocol written to {self.store.path}")
        return protocol

    # ---- steps a subclass may override --------------------------------- #
    def present(self, item: ReviewItem, before: Optional[ReviewFinding], idx: int, total: int) -> None:
        out = self.output_fn
        out("")
        out(f"[{idx}/{total}] {item.record.qualname}   ({item.location})")
        for name, text in item.notes.items():
            out(f"authors' note, {name}: {text}")
        if item.author_verdict:
            out(f"authors' own verdict: {item.author_verdict}")
        for hazard in item.record.hazards:
            out(f"scan, {hazard.kind}: {hazard.reason}")
        if before and before.verdict in VERDICTS:
            out(f"(previously: {before.verdict}{' -- ' + before.note if before.note else ''})")
        out("--- source ---")
        for src_line in item.source.splitlines():
            out(f"    {src_line}")

    def ask_verdict(self, concern, default: Decision) -> Decision:
        """One accept/decline/skip answer; EOF or empty input keeps ``default``."""
        return ask_verdict(self.verdict_prompt.format(concern=concern), default, self.input_fn, self.output_fn)

    def ask_text(self, prompt: str, default: str) -> str:
        """One line of free text; EOF or empty input keeps ``default``."""
        try:
            answer = self.input_fn(prompt).strip()
        except EOFError:
            return default
        return answer or default
