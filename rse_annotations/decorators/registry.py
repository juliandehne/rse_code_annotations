"""Find the concerns: every sub-package of ``decorators/`` whose ``concern.py`` defines ``CONCERN``."""
import importlib
import pkgutil
from pathlib import Path
from typing import Dict

from ._base import Concern


def load() -> Dict[str, Concern]:
    """name -> Concern, in folder order."""
    concerns = {}
    for m in pkgutil.iter_modules([str(Path(__file__).parent)]):
        if m.ispkg:
            c = importlib.import_module(f"{__package__}.{m.name}.concern").CONCERN
            if c.name != m.name:
                raise ValueError(f"concern {c.name!r} lives in folder {m.name!r}")
            if not getattr(c, "assertion", ""):
                raise ValueError(f"concern {c.name!r} sets no assertion")
            concerns[c.name] = c
    return concerns


CONCERNS = load()
