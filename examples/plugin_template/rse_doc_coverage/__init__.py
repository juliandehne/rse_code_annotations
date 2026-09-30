"""Documentation coverage: how much of a research code base explains itself.

Exercise plugin -- the reference for how accessible the plugin API is. Fill in
the TODOs level by level; ``pytest tests`` tells you when a level is done.
"""

from __future__ import annotations

from typing import List

from rse_annotations import Finding, StaticAnalyzer
from rse_annotations.coverage import CoverageReport


class DocCoverageAnalyzer(StaticAnalyzer):
    """Share of functions with a docstring, and the undocumented ones.

    Level 1 (about 1 h): use the static scan you are handed.
        ``report.eligible`` lists every function that counts (dunders, nested
        helpers and test code are already excluded); ``rec.has_docstring`` says
        whether it is documented.
        - one ``info`` finding with rule ``"doc_coverage"`` and the share as
          ``evidence={"coverage": 0.8}``;
        - one ``warn`` finding with rule ``"undocumented"`` per eligible function
          without a docstring (``function=f"{rec.module}.{rec.qualname}"``,
          ``location=rec.location``).
    Level 2 (about 2 h): quality, not just presence.
        Parse ``rec.file`` with :mod:`ast` and flag a docstring that does not
        mention every parameter (``"undocumented_param"``, ``info``). Accept the
        Google (``Args:``), NumPy (``Parameters``) and Sphinx (``:param x:``) styles.
    Level 3 (about 2 h): the project, not just functions.
        Module docstrings, and a README / LICENSE / CITATION.cff next to the code
        (``target.root``). Hint: override :meth:`analyze` to get the target,
        call ``super().analyze(target)`` and append findings.
    """

    name = "docs"
    description = "documentation coverage: docstrings, parameters, README"

    #: Fail the audit (a CI gate) below this share of documented functions.
    threshold = 0.5

    def analyze_scan(self, report: CoverageReport):
        findings: List[Finding] = []
        # TODO level 1: the summary finding and one finding per undocumented function.
        #   Make the summary "fail" instead of "info" when the share < self.threshold.
        # TODO level 2: parameter documentation.
        return self.result(findings, data=report)
