"""Finding analyzers: the built-ins plus any installed plugins.

A plugin is any :class:`~rse_annotations.analysis.base.Analyzer` subclass that a
package advertises in its ``pyproject.toml``::

    [project.entry-points."rse_annotations.analyzers"]
    energy = "my_rse_plugin:EnergyAnalyzer"

After ``pip install my-rse-plugin`` it is listed by ``--list-analyzers`` and runs
alongside the built-ins; nothing in this package has to change.
"""

from __future__ import annotations

from importlib import metadata
from typing import Dict, Iterable, List, Optional, Tuple, Type

from .annotated import ConventionAnalyzer, IOAnalyzer, MathAnalyzer
from .base import PHASES, Analyzer
from .static import CoverageAnalyzer, HazardAnalyzer

ENTRY_POINT_GROUP = "rse_annotations.analyzers"

#: Shipped and implemented, in the order they run.
BUILTIN_ANALYZERS: Tuple[Type[Analyzer], ...] = (
    CoverageAnalyzer, HazardAnalyzer, ConventionAnalyzer, MathAnalyzer, IOAnalyzer,
)


class AnalyzerCatalog:
    """The set of analyzer classes known to this installation, keyed by ``name``."""

    def __init__(self, classes: Iterable[Type[Analyzer]] = ()) -> None:
        self._classes: Dict[str, Type[Analyzer]] = {}
        #: ``(entry point, error)`` for plugins that failed to load.
        self.errors: List[Tuple[str, str]] = []
        for cls in classes:
            self.register(cls)

    def register(self, cls: Type[Analyzer]) -> Type[Analyzer]:
        """Add an analyzer class; also usable as a class decorator."""
        if not (isinstance(cls, type) and issubclass(cls, Analyzer)):
            raise TypeError(f"{cls!r} is not an Analyzer subclass")
        if not cls.name:
            raise ValueError(f"{cls.__name__} has no name")
        if cls.when not in PHASES:
            raise ValueError(f"{cls.__name__}.when must be one of {PHASES}")
        self._classes[cls.name] = cls
        return cls

    def load_entry_points(self, group: str = ENTRY_POINT_GROUP) -> None:
        """Register every analyzer advertised by installed packages."""
        for ep in metadata.entry_points(group=group):
            try:
                self.register(ep.load())
            except Exception as exc:  # noqa: BLE001 - a broken plugin must not break the tool
                self.errors.append((f"{ep.name} = {ep.value}", repr(exc)))

    def names(self) -> List[str]:
        return list(self._classes)

    def get(self, name: str) -> Type[Analyzer]:
        try:
            return self._classes[name]
        except KeyError:
            raise KeyError(f"unknown analyzer {name!r}; known: {', '.join(self._classes)}") from None

    def classes(self) -> List[Type[Analyzer]]:
        return list(self._classes.values())

    def create(self, names: Optional[Iterable[str]] = None, *,
               when: Optional[Iterable[str]] = None) -> List[Analyzer]:
        """Instantiate the selected analyzers (all, by default) with default settings."""
        chosen = [self.get(n) for n in names] if names else self.classes()
        if when is not None:
            phases = set(when)
            chosen = [c for c in chosen if c.when in phases]
        return [cls() for cls in chosen]

    def __contains__(self, name: str) -> bool:
        return name in self._classes

    def __len__(self) -> int:
        return len(self._classes)


def default_catalog(*, plugins: bool = True) -> AnalyzerCatalog:
    """Built-ins, the Responsible-RSE stubs, and (unless ``plugins=False``) installed plugins."""
    from .responsible import RESPONSIBLE_ANALYZERS

    catalog = AnalyzerCatalog(BUILTIN_ANALYZERS + RESPONSIBLE_ANALYZERS)
    if plugins:
        catalog.load_entry_points()
    return catalog
