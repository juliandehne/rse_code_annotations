"""Finding plugins: the ones shipped in :mod:`rse_annotations.plugins` plus installed ones.

A plugin is any :class:`~rse_annotations.core.plugin.Plugin` subclass that a
package advertises in its ``pyproject.toml``::

    [project.entry-points."rse_annotations.plugins"]
    energy = "my_rse_plugin:EnergyPlugin"

After ``pip install my-rse-plugin`` it is listed by ``--list`` and offered in every
mode it implements; nothing in this package has to change.
"""

from __future__ import annotations

from importlib import metadata
from typing import Dict, Iterable, List, Optional, Tuple, Type

from .plugin import MODES, PHASES, Mode, Phase, Plugin

ENTRY_POINT_GROUP = "rse_annotations.plugins"


class PluginCatalog:
    """The set of plugin classes known to this installation, keyed by ``name``."""

    def __init__(self, classes: Iterable[Type[Plugin]] = ()) -> None:
        self._classes: Dict[str, Type[Plugin]] = {}
        #: ``(entry point, error)`` for plugins that failed to load.
        self.errors: List[Tuple[str, str]] = []
        for cls in classes:
            self.register(cls)

    def register(self, cls: Type[Plugin]) -> Type[Plugin]:
        """Add a plugin class; also usable as a class decorator."""
        if not (isinstance(cls, type) and issubclass(cls, Plugin)):
            raise TypeError(f"{cls!r} is not a Plugin subclass")
        if not cls.name:
            raise ValueError(f"{cls.__name__} has no name")
        if cls.when not in PHASES:
            raise ValueError(f"{cls.__name__}.when must be one of {', '.join(PHASES)}")
        if not cls.modes():
            raise ValueError(f"{cls.__name__} implements none of {', '.join(MODES)}")
        self._classes[cls.name] = cls
        return cls

    def load_entry_points(self, group: str = ENTRY_POINT_GROUP) -> None:
        """Register every plugin advertised by installed packages."""
        for ep in metadata.entry_points(group=group):
            try:
                self.register(ep.load())
            except Exception as exc:  # noqa: BLE001 - a broken plugin must not break the tool
                self.errors.append((f"{ep.name} = {ep.value}", repr(exc)))

    def names(self) -> List[str]:
        return list(self._classes)

    def get(self, name: str) -> Type[Plugin]:
        try:
            return self._classes[name]
        except KeyError:
            raise KeyError(f"unknown plugin {name!r}; known: {', '.join(self._classes)}") from None

    def classes(self) -> List[Type[Plugin]]:
        return list(self._classes.values())

    def for_mode(self, mode: str) -> List[Type[Plugin]]:
        """The plugin classes that implement ``mode`` (one of :data:`MODES`)."""
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        return [c for c in self._classes.values() if c.supports(mode)]

    def create(self, names: Optional[Iterable[str]] = None, *,
               when: Optional[Iterable[Phase]] = None,
               mode: Optional[Mode] = None) -> List[Plugin]:
        """Instantiate the selected plugins (all, by default) with default settings."""
        chosen = [self.get(n) for n in names] if names else self.classes()
        return [cls() for cls in filter_plugins(chosen, when=when, mode=mode)]

    def __contains__(self, name: str) -> bool:
        return name in self._classes

    def __len__(self) -> int:
        return len(self._classes)


def filter_plugins(plugins, *, when: Optional[Iterable[Phase]] = None,
                   mode: Optional[Mode] = None) -> list:
    """Keep the plugins (classes or instances) that run in one of ``when`` and offer ``mode``."""
    if mode is not None:
        plugins = [p for p in plugins if p.supports(mode)]
    if when is not None:
        phases = set(when)
        plugins = [p for p in plugins if p.when in phases]
    return list(plugins)


def default_catalog(*, entry_points: bool = True) -> PluginCatalog:
    """The shipped hazard plugins and (unless ``entry_points=False``) installed ones."""
    from ..plugins import BUILTIN_PLUGINS

    catalog = PluginCatalog(BUILTIN_PLUGINS)
    if entry_points:
        catalog.load_entry_points()
    return catalog
