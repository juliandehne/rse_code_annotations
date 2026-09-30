"""Discovery: import a target module/package so its annotations register.

The annotation decorators populate :data:`~rse_annotations.annotations.registry.REGISTRY` as a
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
import importlib.util
import os
import pkgutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable, List

from .registry import REGISTRY, AnnotationInfo

#: Directories never walked when discovering annotations under a path root.
_SKIP_DIRS = {"__pycache__", ".git", ".hg", ".svn", ".venv", "venv", "env",
              "node_modules", ".mypy_cache", ".pytest_cache", "tests", "test_stubs",
              ".ipynb_checkpoints", "build", "dist"}


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


# --------------------------------------------------------------------------- #
# Path-based discovery (no dotted names required)
# --------------------------------------------------------------------------- #

def _iter_python_files(root: Path) -> Iterable[Path]:
    """Yield ``*.py`` files under ``root``, skipping vendored / cache dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        # prune skip dirs and hidden dirs in place so os.walk doesn't descend
        dirnames[:] = [d for d in dirnames
                       if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath) / name


def _module_name_for(path: Path, root: Path) -> str:
    """Derive a dotted module name for ``path`` relative to ``root``."""
    rel = path.relative_to(root).with_suffix("")
    parts = [p for p in rel.parts if p]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) or path.stem


def _import_file(path: Path, module_name: str) -> None:
    """Import a single file by location so its decorators run (idempotent-ish)."""
    if module_name in sys.modules:
        return  # already imported under this name; decorators already ran
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise


def _under_path(file: str, root: Path) -> bool:
    try:
        Path(file).resolve().relative_to(root)
        return True
    except (ValueError, OSError):
        return False


def discover_path(root) -> List[AnnotationInfo]:
    """Discover annotations by walking a directory (no dotted import needed).

    Every ``*.py`` file under ``root`` is imported so its decorators register, then
    the registry is filtered down to annotations whose source file lives under
    ``root``. ``root`` (and its parent) are placed on ``sys.path`` first so intra-
    project imports resolve. Files that fail to import are reported and skipped.

    Args:
        root: Directory to scan (``str`` or ``Path``). Defaults elsewhere to cwd.

    Returns:
        The list of :class:`AnnotationInfo` defined anywhere under ``root``.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory")

    for extra in (str(root), str(root.parent)):
        if extra not in sys.path:
            sys.path.insert(0, extra)

    for path in _iter_python_files(root):
        module_name = _module_name_for(path, root)
        try:
            _import_file(path, module_name)
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # noqa: BLE001 - incl. SystemExit from script-style modules
            print(f"[discovery] warning: could not import {path}: {exc!r}")

    selected: List[AnnotationInfo] = []
    seen: set = set()
    for info in REGISTRY.all():
        if info.file in (None, "<unknown>") or not _under_path(info.file, root):
            continue
        key = (info.module, info.qualname, info.lineno)
        if key in seen:
            continue
        seen.add(key)
        selected.append(info)
    return selected
