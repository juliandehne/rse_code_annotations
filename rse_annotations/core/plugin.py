"""The plugin contract: one class per hazard idea.

Every idea the tool supports -- *has a human inspected the generated code?*, *is
the licence usable?*, *does the pipeline leak test data?* -- is **one**
:class:`Plugin` subclass. A plugin offers up to three capabilities, one per mode
of the general entry point (``python -m rse_annotations``):

* :meth:`Plugin.analyze` -- **hazard analysis**: examine the target and return an
  :class:`~rse_annotations.core.findings.AnalysisResult`; non-interactive, CI-safe.
* :meth:`Plugin.inspect` -- **human inspection**: an interactive session in which a
  person looks at the flagged code and records verdicts.
* :meth:`Plugin.generate_tests` -- **test generation**: write test scaffolds that
  pin what the plugin cares about.

A plugin overrides only the capabilities it has; :meth:`Plugin.modes` reports
which. The machinery a plugin builds on -- the decorators, the AST scan, the
review loop, the stub writer, the renderers -- lives in its own packages
(:mod:`rse_annotations.decorators`, :mod:`~rse_annotations.scan`,
:mod:`~rse_annotations.inspection`, :mod:`~rse_annotations.testing`,
:mod:`~rse_annotations.reporting`) so several plugins can share it.

Built-ins and third-party plugins are the same kind of object. A plugin package
advertises its class under the ``rse_annotations.plugins`` entry-point group (see
:mod:`rse_annotations.core.catalog`).
"""

from __future__ import annotations

from typing import Callable, ClassVar, Optional, Tuple

from .findings import AnalysisResult
from .target import TargetProject

#: When a plugin's analysis runs: over source only, while tests run, while the
#: target runs (see ``ideas/RUNTIME_HAZARDS.md``), or as a gate in CI.
PHASES = ("static", "test", "runtime", "ci")

#: The capabilities a plugin can offer, one per mode of the general entry point.
MODES = ("inspect", "analyze", "generate_tests")

#: Human-readable labels for :data:`MODES`.
MODE_LABELS = {
    "inspect": "Human inspection",
    "analyze": "Hazard analysis",
    "generate_tests": "Test generation",
}


class Plugin:
    """One hazard idea, pluggable into the tool.

    Class attributes a subclass sets:
        name: Unique short identifier, used on the command line (``--plugin licence``).
        description: One line for ``--list``.
        category: Grouping for listings, e.g. ``"hazards"``.
        when: One of :data:`PHASES` -- when :meth:`analyze` can run.
        imports_target: True if :meth:`analyze` imports (and so executes) the target.

    Override any of :meth:`analyze`, :meth:`inspect` and :meth:`generate_tests`.
    """

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    category: ClassVar[str] = "hazards"
    when: ClassVar[str] = "static"
    imports_target: ClassVar[bool] = False

    # ---- capability discovery ------------------------------------------ #
    @classmethod
    def modes(cls) -> Tuple[str, ...]:
        """The :data:`MODES` this plugin implements (the methods it overrides)."""
        return tuple(m for m in MODES if getattr(cls, m) is not getattr(Plugin, m))

    @classmethod
    def supports(cls, mode: str) -> bool:
        return mode in cls.modes()

    def available(self) -> bool:
        """False if the plugin cannot run here; it is then skipped, not failed."""
        return True

    def unavailable_reason(self) -> str:
        """Why :meth:`available` is False -- shown in place of the plugin's findings."""
        return "an optional dependency is not installed"

    # ---- the three capabilities (override what you support) ------------- #
    def analyze(self, target: TargetProject) -> AnalysisResult:
        """Hazard analysis of ``target``."""
        raise NotImplementedError(f"{self.name} does not offer hazard analysis")

    def inspect(self, target: TargetProject, *, input_fn: Callable[[str], str] = input,
                output_fn: Callable[[str], None] = print):
        """Interactive human inspection of ``target``."""
        raise NotImplementedError(f"{self.name} does not offer human inspection")

    def generate_tests(self, target: TargetProject, *, out_dir=None,
                       output_fn: Callable[[str], None] = print):
        """Write test scaffolds for ``target``; returns the written paths."""
        raise NotImplementedError(f"{self.name} does not offer test generation")

    # ---- helpers for subclasses ----------------------------------------- #
    def result(self, findings=None, *, data=None, skipped: Optional[str] = None) -> AnalysisResult:
        return AnalysisResult(self.name, list(findings or []), data=data, skipped=skipped)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name!r} ({', '.join(self.modes()) or 'no modes'})>"
