"""Discovery: import a target module/package so its annotations register.

The annotation decorators populate :data:`~rse_annotations.registry.REGISTRY` as a
side effect of *import*. So "discovery" is just: import everything under the target,
then read back the registry.

Note on Python's module cache: importing a module only runs its top-level code
(and therefore its decorators) the *first* time. A second ``import_module`` of an
already-loaded module returns the cached object without re-executing anything. So
we must NOT clear the global registry and expect a re-import to repopulate it --
it won't. Instead we import (idempotently), then *filter* the registry down to the
annotations whose defining module falls under the requested target(s). This is
correct whether the target was imported for the first time just now or long ago.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Iterable, List

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


def _under_target(module_name: str, target: str) -> bool:
    """True if ``module_name`` is ``target`` itself or a submodule of it."""
    return module_name == target or module_name.startswith(target + ".")


def _select_for_targets(targets: Iterable[str]) -> List[AnnotationInfo]:
    """Registry entries whose defining module lies under any of ``targets``.

    Preserves registration order and de-duplicates across overlapping targets
    (e.g. a package and one of its submodules).
    """
    targets = list(targets)
    selected: List[AnnotationInfo] = []
    seen: set = set()
    for info in REGISTRY.all():
        if not any(_under_target(info.module, t) for t in targets):
            continue
        key = (info.module, info.qualname, info.lineno)
        if key in seen:
            continue
        seen.add(key)
        selected.append(info)
    return selected


def discover(target: str, *, clear: bool = True) -> List[AnnotationInfo]:
    """Import ``target`` (dotted module/package path) and return its annotations.

    Args:
        target: Importable dotted path, e.g. ``"examples.sample_pipeline"``.
        clear: Accepted for backward compatibility and ignored. Results are
            already scoped to ``target`` by filtering the registry, so no global
            reset is needed (and a reset would be unsafe -- see the module note).

    Returns:
        The list of :class:`AnnotationInfo` defined under ``target``.
    """
    module = importlib.import_module(target)
    _import_all_submodules(module)
    return _select_for_targets([target])


def discover_many(targets: Iterable[str], *, clear: bool = True) -> List[AnnotationInfo]:
    """Import several targets and return the combined annotations under them.

    Args:
        targets: importable dotted paths.
        clear: accepted for backward compatibility and ignored (see :func:`discover`).

    Returns:
        The combined, de-duplicated list of :class:`AnnotationInfo` across all
        targets, in registration order.
    """
    targets = list(targets)
    for target in targets:
        module = importlib.import_module(target)
        _import_all_submodules(module)
    return _select_for_targets(targets)
