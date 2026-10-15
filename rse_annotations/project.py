"""The project under audit: the code to scan, the concerns to look for, and its verdicts."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from .analysis.scan import Record, scan
from .decorators import Concern
from .inspection import verdicts as vs

SKIP_DIRS = {"__pycache__", "venv", "env", "node_modules", "tests", "build", "dist"}


@dataclass(frozen=True)
class Project:
    """A directory (or one ``.py`` file) audited for ``concerns`` (from ``decorators.load()``).

    The code is only parsed, never imported. Verdicts live in ``inspection.yaml`` next to it.
    """

    root: Path
    concerns: Dict[str, Concern]

    def __post_init__(self):
        object.__setattr__(self, "root", Path(self.root).resolve())

    @property
    def base(self) -> Path:
        """The directory that locations are relative to."""
        return self.root.parent if self.root.is_file() else self.root

    @property
    def verdict_file(self) -> Path:
        return self.base / vs.VERDICT_FILE

    def files(self) -> Iterator[Path]:
        """Every ``*.py`` file to scan; tests, ``setup.py`` and tool directories are skipped."""
        if self.root.is_file():
            yield self.root
            return
        for dirpath, dirs, files in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            for f in sorted(files):
                if f.endswith(".py") and not f.startswith("test_") and f not in ("conftest.py", "setup.py"):
                    yield Path(dirpath) / f

    def scan(self) -> Tuple[List[Record], List[str]]:
        """(records, parse errors) for every function in :meth:`files`."""
        return scan(self)

    def verdicts(self) -> List[vs.Verdict]:
        """The verdicts saved so far (none if there is no verdict file yet)."""
        return vs.load(self.verdict_file)

    def save(self, verdicts: List[vs.Verdict]) -> None:
        self.verdict_file.write_text(vs.dump(verdicts), encoding="utf-8")
