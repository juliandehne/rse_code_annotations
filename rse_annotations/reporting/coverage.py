"""Text and Markdown rendering of a :class:`~rse_annotations.scan.CoverageReport`."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..annotations.registry import KINDS
from ..scan.hazards import (_HAZARD_PRIORITY, CRITICAL_HAZARDS, HAZARD_HELP, HAZARD_PARENT,
                            HAZARDS, Hazard)
from ..scan.model import CoverageReport, FunctionRecord


def _table(headers: List[str], rows: List[List[str]]) -> str:
    """Render a fixed-width text table (no dependencies)."""
    if not rows:
        return "  (none)"
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip()
    rule = "  ".join("-" * w for w in widths).rstrip()
    out = [line, rule]
    for row in rows:
        out.append("  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip())
    return "\n".join(out)


def _rel(report: CoverageReport, file: str) -> str:
    try:
        return str(Path(file).relative_to(report.root)).replace("\\", "/")
    except ValueError:
        return file


def _critical_hazard(rec: FunctionRecord) -> Optional[Hazard]:
    """The record's worst *direct* provenance hazard, or ``None``.

    Inherited (``indirect``) hazards are excluded on purpose: propagation is what makes
    the map complete, and a shortlist is only useful if it names the function that
    actually does the dangerous thing.
    """
    for kind in CRITICAL_HAZARDS:
        h = rec.hazard(kind)
        if h is not None and not h.indirect:
            return h
    return None


def render_coverage_text(report: CoverageReport, *, max_candidates: int = 25) -> str:
    """Render the coverage table and candidate worklist for the console."""
    eligible, annotated = len(report.eligible), len(report.annotated)
    lines = [
        f"Annotation coverage for {report.root}",
        f"  {report.files_scanned} file(s), {len(report.records)} function(s)/method(s) found; "
        f"{eligible} eligible (dunders, nested helpers and tests excluded)",
        f"  annotated: {annotated}/{eligible}  ({report.coverage:.0%})",
        "",
        "By annotation kind",
    ]
    present, suggested = report.counts_by_kind(), report.suggested_by_kind()
    lines.append(_table(
        ["kind", "annotated", "candidates"],
        [[f"@{k}", str(present[k]), str(suggested[k])] for k in KINDS],
    ))

    lines += ["", "By file"]
    rows = []
    for file, recs in sorted(report.by_file().items()):
        elig = [r for r in recs if r.eligible]
        ann = [r for r in recs if r.annotated]
        cand = [r for r in recs if r.is_candidate]
        if not elig:
            continue
        pct = f"{len(ann) / len(elig):.0%}"
        rows.append([_rel(report, file), str(len(elig)), str(len(ann)), pct, str(len(cand))])
    lines.append(_table(["file", "funcs", "annotated", "coverage", "candidates"], rows))

    if report.hazardous:
        haz = report.counts_by_hazard()
        lines += ["", f"Audit hazards ({len(report.hazardous)}/{eligible} eligible functions, "
                      f"{report.hazard_rate:.0%})",
                  "  Orthogonal to the four annotations: not 'where does data flow?' but",
                  "  'where can the result be wrong, and can I reproduce it?' (proposed, not yet enforced)"]
        lines.append(_table(
            ["hazard", "n", "specialises", "what it means"],
            [[f"@{h}", str(haz[h]),
              f"@{HAZARD_PARENT[h]}" if HAZARD_PARENT[h] else "--",
              HAZARD_HELP[h]] for h in HAZARDS if haz[h]],
        ))

        worst = [r for r in report.hazardous if _critical_hazard(r)]
        if worst:
            lines += ["", f"Reproducibility-critical ({len(worst)})"]
            lines.append(_table(
                ["hazards", "function", "location", "why"],
                [[",".join(h.kind for h in r.hazards), r.qualname,
                  f"{_rel(report, r.file)}:{r.lineno}",
                  _critical_hazard(r).reason] for r in worst[:max_candidates]],
            ))
            if len(worst) > max_candidates:
                lines.append(f"  ... and {len(worst) - max_candidates} more (see the written report)")

    cands = report.candidates
    lines += ["", f"Candidates for annotation ({len(cands)})"]
    shown = cands[:max_candidates]
    lines.append(_table(
        ["suggest", "conf", "function", "location", "why"],
        [[f"@{c.suggested}", c.confidence, c.qualname,
          f"{_rel(report, c.file)}:{c.lineno}", c.reason] for c in shown],
    ))
    if len(cands) > len(shown):
        lines.append(f"  ... and {len(cands) - len(shown)} more (see the written report)")

    if report.parse_errors:
        lines += ["", f"Could not parse {len(report.parse_errors)} file(s):"]
        lines += [f"  {_rel(report, f)}: {e}" for f, e in report.parse_errors]
    return "\n".join(lines)


def render_coverage_markdown(report: CoverageReport) -> str:
    """Render the full report (every candidate, no truncation) as Markdown."""
    eligible, annotated = len(report.eligible), len(report.annotated)
    present, suggested = report.counts_by_kind(), report.suggested_by_kind()

    out = [
        "# Annotation coverage",
        "",
        f"Static (AST) scan of `{report.root}` — nothing imported, nothing executed.",
        "",
        f"- files scanned: **{report.files_scanned}**",
        f"- functions/methods found: **{len(report.records)}** "
        f"({eligible} eligible; dunders, nested helpers and tests excluded)",
        f"- annotated: **{annotated}/{eligible}** (**{report.coverage:.0%}** coverage)",
        f"- candidates for annotation: **{len(report.candidates)}**",
        "",
        "## Coverage by kind",
        "",
        "| Annotation | Present | Candidates |",
        "| --- | ---: | ---: |",
    ]
    out += [f"| `@{k}` | {present[k]} | {suggested[k]} |" for k in KINDS]

    out += ["", "## Coverage by file", "",
            "| File | Functions | Annotated | Coverage | Candidates |",
            "| --- | ---: | ---: | ---: | ---: |"]
    for file, recs in sorted(report.by_file().items()):
        elig = [r for r in recs if r.eligible]
        if not elig:
            continue
        ann = [r for r in recs if r.annotated]
        cand = [r for r in recs if r.is_candidate]
        out.append(f"| `{_rel(report, file)}` | {len(elig)} | {len(ann)} | "
                   f"{len(ann) / len(elig):.0%} | {len(cand)} |")

    if report.annotated:
        out += ["", "## Already annotated", "",
                "| Function | File | Annotation |", "| --- | --- | --- |"]
        for r in sorted(report.annotated, key=lambda r: (r.file, r.lineno)):
            out.append(f"| `{r.qualname}` | `{_rel(report, r.file)}:{r.lineno}` | `@{r.kind}` |")

    if report.hazardous:
        haz = report.counts_by_hazard()
        out += ["", "## Audit hazards", "",
                "A second, **orthogonal** axis (proposed — detected here, not yet enforced). The "
                "four annotations answer *where does data flow?*; these answer *where can the "
                "result be wrong, and can I reproduce it?* A function has one dataflow role and "
                "zero or more hazards.", "",
                f"**{len(report.hazardous)} of {eligible}** eligible functions "
                f"(**{report.hazard_rate:.0%}**) carry at least one hazard.", "",
                "| Hazard | Found | Specialises | What it means |",
                "| --- | ---: | --- | --- |"]
        for h in HAZARDS:
            parent = f"`@{HAZARD_PARENT[h]}`" if HAZARD_PARENT[h] else "—"
            out.append(f"| `@{h}` | {haz[h]} | {parent} | {HAZARD_HELP[h]} |")

        out += ["", "### Hazardous functions", "",
                "`indirect` means the hazard was inherited through the call graph — the "
                "function does not touch the model/RNG itself, but everything it returns "
                "depends on one.", "",
                "| Hazards | Function | Location | Role | Evidence |",
                "| --- | --- | --- | --- | --- |"]
        for r in report.hazardous:
            kinds = ", ".join(f"`@{h.kind}`" + ("*" if h.indirect else "")
                              for h in sorted(r.hazards, key=lambda x: _HAZARD_PRIORITY[x.kind]))
            role = f"`@{r.kind}`" if r.kind else (f"`@{r.suggested}`?" if r.suggested else "—")
            why = "; ".join(h.reason for h in sorted(
                r.hazards, key=lambda x: _HAZARD_PRIORITY[x.kind])[:2])
            out.append(f"| {kinds} | `{r.qualname}` | `{_rel(report, r.file)}:{r.lineno}` | "
                       f"{role} | {why} |")
        out += ["", "`*` = inherited through the call graph (indirect)."]

    out += ["", "## Candidates", "",
            "Heuristic suggestions from the syntax alone — a worklist for review, "
            "not a verdict.", "",
            "| Suggested | Confidence | Function | Location | Why |",
            "| --- | --- | --- | --- | --- |"]
    for c in report.candidates:
        out.append(f"| `@{c.suggested}` | {c.confidence} | `{c.qualname}` | "
                   f"`{_rel(report, c.file)}:{c.lineno}` | {c.reason} |")

    skipped = [r for r in report.records
               if r.eligible and r.kind is None and r.suggested is None]
    if skipped:
        out += ["", "## Not candidates", "",
                "Eligible functions we deliberately do *not* propose an annotation for.",
                "", "| Function | Location | Reason |", "| --- | --- | --- |"]
        for r in sorted(skipped, key=lambda r: (r.file, r.lineno)):
            out.append(f"| `{r.qualname}` | `{_rel(report, r.file)}:{r.lineno}` | {r.reason} |")

    if report.parse_errors:
        out += ["", "## Parse errors", ""]
        out += [f"- `{_rel(report, f)}`: {e}" for f, e in report.parse_errors]

    return "\n".join(out) + "\n"


def write_coverage_report(target, output_fn=print, *, name: str = "annotation_coverage.md") -> int:
    """Print the static coverage report of ``target`` and write the full one next to it.

    Never imports the target, so it also works on code that does not load.
    """
    report = target.static_scan()
    output_fn("")
    output_fn(render_coverage_text(report))
    out_path = target.output_path(name)
    out_path.write_text(render_coverage_markdown(report), encoding="utf-8")
    output_fn("")
    output_fn(f"Full report (every candidate) written to {out_path}")
    return 0
