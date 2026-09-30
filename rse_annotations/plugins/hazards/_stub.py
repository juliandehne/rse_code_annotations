"""The base class every not-yet-implemented hazard plugin derives from.

A stub is a registered, listable plugin that does nothing yet. It declares the
*hazard analysis* mode, but ``available()`` is False, so an
:class:`~rse_annotations.core.audit.Audit` reports it as *skipped* with the reason
"not implemented yet", and ``--list`` shows it with its tier.

How to implement one (course task)
----------------------------------
1. Read the class docstring (the TODO spec) and the matching section of
   ``ideas/RESPONSIBLE_RSE_PLUGINS.md`` (``proposal`` attribute);
   ``ideas/EVERSE_MAPPING.md`` lists the matching EVERSE indicators, RSQKit pages and
   tools to reuse or cite. ``difficulty`` (1-5) is the expected workload in hours per
   week over a semester.
2. Change the base class from :class:`HazardStub` to
   :class:`~rse_annotations.core.plugin.Plugin` and implement ``analyze(target)``.
   Reuse the shared machinery instead of writing your own:
   ``target.static_scan()`` (the AST scan of every function, never imports the target,
   :mod:`rse_annotations.scan`), ``target.annotations()`` (the annotated functions,
   imports the target), ``target.iter_python_files()`` (the raw tree).
3. Optionally add the other two modes: ``inspect(target, input_fn=, output_fn=)`` for an
   interactive human review (see :mod:`rse_annotations.inspection.review`) and
   ``generate_tests(target, out_dir=)`` for test scaffolds (see
   :mod:`rse_annotations.testing`). The general entry point offers your plugin in every
   mode it implements.
4. Keep ``name``, ``when``, ``description`` and ``question``; drop the stub-only
   attributes if you like. A ``when = "runtime"`` hazard (energy, inference counts) reads
   a ledger recorded while the code ran -- see ``ideas/RUNTIME_HAZARDS.md``.
5. If you need an optional dependency, override ``available()`` to return False when it
   is missing and ``unavailable_reason()`` to say what to ``pip install``.
6. Return findings via ``self.result([...])``; add tests in ``tests/``.
"""

from __future__ import annotations

from typing import ClassVar, Tuple

from ...core.plugin import Plugin

NOT_IMPLEMENTED = "not implemented yet — student task (Responsible RSE course)"


class HazardStub(Plugin):
    """A placeholder hazard plugin from the Responsible-RSE proposal."""

    category: ClassVar[str] = "hazards"
    #: The Responsible-RSE question the hazard belongs to.
    question: ClassVar[str] = ""
    #: A = build first (small, high value), B = next, C = optional/extension.
    tier: ClassVar[str] = "C"
    #: S / M / L student effort estimate.
    effort: ClassVar[str] = "S"
    #: Expected student workload, 1-5 = roughly 1-5 hours per week over a ~12-14 week
    #: semester, to implement the check at a reasonable level *with tests*.
    #: 1 = a rules file / pattern list; 3 = new kwargs, a third-party tool and some design;
    #: 5 = runtime instrumentation plus research-level validation.
    difficulty: ClassVar[int] = 3
    #: Section of ideas/RESPONSIBLE_RSE_PLUGINS.md with the full proposal.
    proposal: ClassVar[str] = ""
    #: Annotations / hazards the plugin hooks into.
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
