"""Running plugins over one :class:`~rse_annotations.core.target.TargetProject`.

::

    from rse_annotations import Audit, TargetProject, TextRenderer

    audit = Audit(TargetProject.parse("https://github.com/org/repo"))
    report = audit.run(only=["human_code_inspection"])     # hazard analysis
    print(TextRenderer().render_results(report.results))

    audit.plugin("human_code_inspection").inspect(audit.target)          # human inspection
    audit.plugin("human_code_inspection").generate_tests(audit.target)   # test generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from .catalog import PluginCatalog, default_catalog, filter_plugins
from .findings import AnalysisResult, Finding
from .plugin import Plugin
from .target import TargetProject


@dataclass
class AuditReport:
    """The results of every plugin that took part in one :meth:`Audit.run`."""

    target: str
    results: List[AnalysisResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    def result(self, plugin: str) -> AnalysisResult:
        for r in self.results:
            if r.plugin == plugin:
                return r
        raise KeyError(plugin)

    def to_dict(self) -> dict:
        return {"target": self.target, "ok": self.ok,
                "results": [r.to_dict() for r in self.results]}


class Audit:
    """Runs the hazard analysis of the selected plugins over a target.

    Args:
        target: The project under audit.
        catalog: Where plugins come from; defaults to the shipped ones + installed ones.
        plugins: Explicit (e.g. configured) plugin instances; they replace the
            catalog's default instances.
    """

    def __init__(self, target: TargetProject, *, catalog: Optional[PluginCatalog] = None,
                 plugins: Optional[List[Plugin]] = None) -> None:
        self.target = target
        self.catalog = catalog if catalog is not None else default_catalog()
        self.plugins = plugins

    def select(self, only: Optional[Iterable[str]] = None,
               when: Optional[Iterable[str]] = None,
               mode: Optional[str] = "analyze") -> List[Plugin]:
        """The plugin instances to use, filtered by name, phase and mode."""
        if self.plugins is None:
            return self.catalog.create(only, when=when, mode=mode)
        wanted = set(only or ())
        chosen = [p for p in self.plugins if not wanted or p.name in wanted]
        return filter_plugins(chosen, when=when, mode=mode)

    def plugin(self, name: str) -> Plugin:
        """One plugin instance by name (a configured one if given, else a default one)."""
        for p in self.plugins or ():
            if p.name == name:
                return p
        return self.catalog.get(name)()

    def run(self, only: Optional[Iterable[str]] = None,
            when: Optional[Iterable[str]] = None) -> AuditReport:
        """Hazard analysis with every selected plugin. Unavailable plugins are reported
        as skipped; a plugin that crashes yields one ``fail`` finding instead of aborting."""
        report = AuditReport(self.target.name)
        for plugin in self.select(only, when):
            report.results.append(self.run_one(plugin))
        return report

    def run_one(self, plugin: Plugin) -> AnalysisResult:
        if not plugin.available():
            return plugin.result(skipped=plugin.unavailable_reason())
        try:
            return plugin.analyze(self.target)
        except Exception as exc:  # noqa: BLE001 - one broken plugin must not stop the audit
            return plugin.result([Finding("plugin_error", "fail",
                                          f"{type(exc).__name__}: {exc}")])
