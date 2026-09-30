"""The base class every Responsible-RSE stub derives from.

A stub is a registered, listable analyzer that does nothing yet: ``available()`` is
False, so an :class:`~rse_annotations.audit.Audit` reports it as *skipped* with the
reason "not implemented yet", and ``--list-analyzers`` shows it with its tier.

How to implement one (course task)
----------------------------------
1. Read the class docstring (the TODO spec) and the matching section of
   ``RESPONSIBLE_RSE_PLUGINS.md`` (``proposal`` attribute); ``EVERSE_MAPPING.md`` lists
   the matching EVERSE indicators, RSQKit pages and tools to reuse or cite.
   ``difficulty`` (1-5) is the expected workload in hours per week over a semester.
2. Change the base class from :class:`ResponsibleRSEStub` to the base that fits:
   :class:`~rse_annotations.analysis.base.StaticAnalyzer` (AST scan, never imports the
   target -- implement ``analyze_scan(report)``),
   :class:`~rse_annotations.analysis.base.AnnotationAnalyzer` (per annotated function --
   set ``kinds`` and implement ``analyze_function(info)``), or plain
   :class:`~rse_annotations.analysis.base.Analyzer` (implement ``analyze(target)``).
3. Keep ``name``, ``when`` and ``description``; drop the stub-only attributes if you like.
4. If you need an optional dependency, override ``available()`` to return False when it
   is missing and ``unavailable_reason()`` to say what to ``pip install``.
5. Return findings via ``self.result([...])``; add tests in ``tests/``.
"""

from __future__ import annotations

from typing import ClassVar, Tuple

from ..base import Analyzer

NOT_IMPLEMENTED = "not implemented yet — student task (Responsible RSE course)"


class ResponsibleRSEStub(Analyzer):
    """A placeholder analyzer from the Responsible-RSE plugin proposal."""

    #: A = build first (small, high value), B = next, C = optional/extension.
    tier: ClassVar[str] = "C"
    #: S / M / L student effort estimate.
    effort: ClassVar[str] = "S"
    #: Expected student workload, 1-5 = roughly 1-5 hours per week over a ~12-14 week
    #: semester, to implement the check at a reasonable level *with tests*.
    #: 1 = a rules file / pattern list; 3 = new kwargs, a third-party tool and some design;
    #: 5 = runtime instrumentation plus research-level validation.
    difficulty: ClassVar[int] = 3
    #: Section of RESPONSIBLE_RSE_PLUGINS.md with the full proposal.
    proposal: ClassVar[str] = ""
    #: Annotations / hazards the analyzer hooks into.
    hooks: ClassVar[Tuple[str, ...]] = ()
    #: Suggested third-party tools (all optional dependencies).
    tools: ClassVar[Tuple[str, ...]] = ()

    def available(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return NOT_IMPLEMENTED

    def analyze(self, target):
        raise NotImplementedError(
            f"{type(self).__name__} is a stub; see its docstring and {self.proposal}")
