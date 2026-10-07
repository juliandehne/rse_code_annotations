"""Turning analysis results and review verdicts into something a person reads.

One :class:`Renderer` per output format. Every renderer handles both things the tool
shows a person: the machine's :class:`~rse_annotations.findings.AnalysisResult` list
and the human's :class:`~rse_annotations.inspection.verdicts.Verdict` list. Add a format by
subclassing :class:`Renderer`.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from .coverage import render_coverage_markdown
from ..core.findings import SEVERITIES, AnalysisResult, Severity, Status
from ..inspection.verdicts import Verdict, count_verdicts, verdict_summary
from ..textenum import TextEnum
from ..scan.model import CoverageReport

def _coverage_of(data) -> Optional[CoverageReport]:
    """The coverage report a plugin's ``data`` carries, if any (duck-typed)."""
    for candidate in (data, getattr(data, "coverage", None)):
        if isinstance(candidate, CoverageReport):
            return candidate
    return None


class OutputFormat(TextEnum):
    """The formats a report can be written in; :data:`RENDERERS` has one renderer each."""

    TEXT = "text"
    MARKDOWN = "markdown"
    JSON = "json"


class Renderer(ABC):
    """One output format for results and verdicts."""

    #: File extension a caller can use when writing the rendered text to disk.
    suffix = ".txt"

    @abstractmethod
    def render_results(self, results: Sequence[AnalysisResult]) -> str:
        """Render the findings of one audit."""

    @abstractmethod
    def render_verdicts(self, verdicts: Sequence[Verdict]) -> str:
        """Render the human verdicts recorded in ``inspection.yaml``."""


class TextRenderer(Renderer):
    """Plain text for the terminal. ``info`` findings are hidden unless ``verbose``."""

    def __init__(self, *, verbose: bool = False) -> None:
        self.verbose = verbose

    def render_results(self, results: Sequence[AnalysisResult]) -> str:
        lines: List[str] = []
        for r in results:
            head = f"[{r.status.mark}] {r.plugin}"
            if r.skipped:
                lines.append(f"{head}: {r.skipped}")
                continue
            counts = ", ".join(f"{r.count(s)} {s}" for s in SEVERITIES if r.count(s))
            lines.append(f"{head}: {counts or 'no findings'}")
            for f in r.findings:
                if f.severity == Severity.INFO and not self.verbose:
                    continue
                where = f"  {f.function}" if f.function else ""
                lines.append(f"    {f.severity:<4} {f.rule}{where}: {f.message}")
        failed = sum(1 for r in results if r.status == Status.FAIL)
        lines.append("")
        lines.append(f"{len(results)} plugin(s) run, {failed} failed.")
        return "\n".join(lines)

    def render_verdicts(self, verdicts: Sequence[Verdict]) -> str:
        if not verdicts:
            return "No verdicts recorded."
        lines = [f"{v.verdict:<9} {v.function}   ({v.location})\n          {v.formula}"
                 for v in verdicts]
        lines.append(f"{len(verdicts)} verdict(s): {verdict_summary(verdicts)}")
        return "\n".join(lines)


class MarkdownRenderer(Renderer):
    """Markdown for reports that go next to the code or into a paper appendix.

    A result whose ``data`` carries a :class:`~rse_annotations.scan.CoverageReport`
    (as ``data`` itself or as ``data.coverage``) is rendered with the full coverage
    report, as ``decorator_coverage.md`` holds it; the findings follow.
    """

    suffix = ".md"

    def render_results(self, results: Sequence[AnalysisResult]) -> str:
        parts = ["# Audit report", "",
                 "| Plugin | Status | fail | warn | info |", "|---|---|---:|---:|---:|"]
        for r in results:
            parts.append(f"| {r.plugin} | {r.status} | {r.count(Severity.FAIL)} | "
                         f"{r.count(Severity.WARN)} | {r.count(Severity.INFO)} |")
        for r in results:
            parts += ["", f"## {r.plugin}", ""]
            if r.skipped:
                parts.append(f"_Skipped: {r.skipped}_")
                continue
            coverage = _coverage_of(r.data)
            if coverage is not None:
                parts.append(render_coverage_markdown(coverage))
                parts.append("")
            if not r.findings:
                parts.append("No findings.")
            else:
                for f in r.findings:
                    where = f" `{f.function}`" if f.function else ""
                    parts.append(f"- **{f.severity}** `{f.rule}`{where}: {f.message}")
        return "\n".join(parts) + "\n"

    def render_verdicts(self, verdicts: Sequence[Verdict]) -> str:
        parts = ["# Review verdicts", "", "| Function | Location | Formula | Verdict |",
                 "|---|---|---|---|"]
        for v in verdicts:
            formula = v.formula.replace("|", "\\|")
            parts.append(f"| `{v.function}` | {v.location} | `{formula}` | {v.verdict} |")
        parts += ["", f"{len(verdicts)} verdict(s): {verdict_summary(verdicts)}"]
        return "\n".join(parts) + "\n"


class JsonRenderer(Renderer):
    """JSON for CI and other tools."""

    suffix = ".json"

    def __init__(self, *, indent: int = 2) -> None:
        self.indent = indent

    def render_results(self, results: Sequence[AnalysisResult]) -> str:
        return json.dumps({"ok": all(r.ok for r in results),
                           "results": [r.to_dict() for r in results]}, indent=self.indent)

    def render_verdicts(self, verdicts: Sequence[Verdict]) -> str:
        return json.dumps({"summary": count_verdicts(verdicts),
                           "verdicts": [vars(v) for v in verdicts]}, indent=self.indent)


#: The renderer class of every :class:`OutputFormat`.
RENDERERS = {OutputFormat.TEXT: TextRenderer, OutputFormat.MARKDOWN: MarkdownRenderer,
             OutputFormat.JSON: JsonRenderer}
