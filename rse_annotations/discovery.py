"""Discovery: import a target module/package so its annotations register.

The annotation decorators populate :data:`~rse_annotations.registry.REGISTRY` as a
side effect of *import*. So "discovery" is just: import everything under the target,
then read the registry.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import List

from .registry import REGISTRY, AnnotationInfo


def _import_all_submodules(module: ModuleType) -> None:
    """Recursively import every submodule of a package so all decorators run."""
    if not hasattr(module, "__path__"):
        return  # a plain module, nothing to walk
    for info in pkgutil.walk_packages(module.__path__, prefix=module.__name__ + "."):
        try:
            importlib.import_module(info.name)
        except Exception as exc:  # noqa: BLE001 - report and continue
            # A broken submodule shouldn't abort discovery of the rest.
            print(f"[discovery] warning: could not import {info.name}: {exc}")


def discover(target: str, *, clear: bool = True) -> List[AnnotationInfo]:
    """Import ``target`` (dotted module/package path) and return annotated functions.

    Args:
        target: Importable dotted path, e.g. ``"examples.sample_pipeline"``.
        clear: Reset the registry first so results reflect only this target.

    Returns:
        The list of :class:`AnnotationInfo` collected from the target.
    """
    if clear:
        REGISTRY.clear()
    module = importlib.import_module(target)
    _import_all_submodules(module)
    return REGISTRY.all()
