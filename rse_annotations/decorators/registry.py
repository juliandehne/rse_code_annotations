"""Find the concerns: one instance per sub-package of ``decorators/``.

As in Java, the file is named after the class it implements: folder ``hardware_dependency``
holds ``HardwareDependency.py`` with ``class HardwareDependency(Concern)``. The registry
creates the one instance, ``HardwareDependency("hardware_dependency")``: that instance is
the decorator users import.
"""
import importlib
import pkgutil
from pathlib import Path
from typing import Dict

from ._base import Concern


def class_name(folder: str) -> str:
    """``hardware_dependency`` -> ``HardwareDependency``."""
    return "".join(part.capitalize() for part in folder.split("_"))


def load() -> Dict[str, Concern]:
    """name -> Concern, in folder order."""
    concerns = {}
    for m in pkgutil.iter_modules([str(Path(__file__).parent)]):
        if m.ispkg:
            cls = class_name(m.name)
            sub = getattr(importlib.import_module(f"{__package__}.{m.name}.{cls}"), cls, None)
            if not (isinstance(sub, type) and issubclass(sub, Concern)):
                raise ValueError(f"{m.name}/{cls}.py must define class {cls}(Concern)")
            c = sub(m.name)
            if not getattr(c, "assertion", ""):
                raise ValueError(f"concern {c.name!r} sets no assertion")
            concerns[c.name] = c
    return concerns


CONCERNS = load()
