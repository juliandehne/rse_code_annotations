"""Find the concerns: one instance per sub-package of ``decorators/``.

As in Java, the file is named after the class it implements: folder ``hardware_dependency``
holds ``HardwareDependency.py`` with ``class HardwareDependency(Concern)``. The registry
creates the one instance, ``HardwareDependency("hardware_dependency")``: that instance is
the decorator users import.

Nothing happens on import. :func:`load` is called explicitly by the runner; the package's
``__getattr__`` calls :func:`load_one` for ``from rse_annotations import <concern>``.
"""
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List

from ._base import Concern


def class_name(folder: str) -> str:
    """``hardware_dependency`` -> ``HardwareDependency``."""
    return "".join(part.capitalize() for part in folder.split("_"))


def names() -> List[str]:
    """The concern names: the sub-package folders of ``decorators/``."""
    return [m.name for m in pkgutil.iter_modules([str(Path(__file__).parent)]) if m.ispkg]


def load_one(name: str) -> Concern:
    """Import ``<name>/<ClassName>.py`` and create its one instance."""
    cls = class_name(name)
    sub = getattr(importlib.import_module(f"{__package__}.{name}.{cls}"), cls, None)
    if not (isinstance(sub, type) and issubclass(sub, Concern)):
        raise ValueError(f"{name}/{cls}.py must define class {cls}(Concern)")
    c = sub(name)
    if not getattr(c, "assertion", ""):
        raise ValueError(f"concern {name!r} sets no assertion")
    return c


def load() -> Dict[str, Concern]:
    """name -> Concern for every concern folder, in folder order."""
    return {name: load_one(name) for name in names()}
