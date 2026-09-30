"""The project under analysis.

A :class:`TargetProject` is the one object every analyzer, reviewer, renderer and
test generator receives. It knows *where* the research code lives -- a local
directory, or a git URL that is cloned on first use -- and caches the two expensive
views of it that several plugins share:

* :meth:`TargetProject.decorated` -- the decorated functions, found by *importing*
  the code (:func:`~rse_annotations.decorators.discovery.discover_path`);
* :meth:`TargetProject.static_scan` -- the AST scan of every function, which never
  imports anything (:func:`~rse_annotations.scan.scan_path`).

Usage::

    TargetProject.from_path("src/")
    TargetProject.from_url("https://github.com/org/repo", ref="v1.2")
    TargetProject.from_modules(["pkg.pipeline"])   # importable dotted module names
    TargetProject.parse(spec)        # a path or a URL, as typed on the command line
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator, List, Optional, Union

import importlib.util

from ..decorators.discovery import _iter_python_files, discover_many, discover_path
from ..decorators.registry import DecoratorInfo

_URL_RE = re.compile(r"^(https?|git|ssh|file)://|^git@[^:]+:")


class TargetProject:
    """A body of research code identified by a local path, a git URL, or module names.

    Args:
        path: Local directory holding the code. If ``url`` is also given, this is
            where the clone goes (created on first use).
        url: Git URL to clone when there is no local copy yet.
        ref: Branch or tag to check out when cloning.
        name: Display name; defaults to the directory or repository name.
        modules: Importable dotted module names (packages include their
            submodules). Decorators are then discovered by importing these
            instead of every file under ``path``.
    """

    def __init__(
        self,
        path: Union[str, Path, None] = None,
        *,
        url: Optional[str] = None,
        ref: Optional[str] = None,
        name: Optional[str] = None,
        modules: Optional[List[str]] = None,
    ) -> None:
        if path is None and url is None and not modules:
            raise ValueError("a TargetProject needs a path, a url or modules")
        self.url = url
        self.ref = ref
        self.modules = list(modules) if modules else None
        if path is None and self.modules:
            path = _module_dir(self.modules[0])
        self._path = Path(path).resolve() if path is not None else None
        self.name = name or (", ".join(self.modules) if self.modules else
                             self._path.name if self._path else _repo_name(url))
        self._decorated: Optional[List[DecoratorInfo]] = None
        self._scan = None

    # ---- construction --------------------------------------------------- #
    @classmethod
    def from_path(cls, path: Union[str, Path], **kw) -> "TargetProject":
        return cls(path, **kw)

    @classmethod
    def from_url(cls, url: str, *, ref: Optional[str] = None,
                 into: Union[str, Path, None] = None, **kw) -> "TargetProject":
        return cls(into, url=url, ref=ref, **kw)

    @classmethod
    def from_modules(cls, modules: Union[str, List[str]], **kw) -> "TargetProject":
        """A target made of importable modules, e.g. ``"examples.sample_pipeline"``."""
        return cls(modules=[modules] if isinstance(modules, str) else list(modules), **kw)

    @classmethod
    def parse(cls, spec: str, **kw) -> "TargetProject":
        """Build a target from a command-line string: a URL or a directory."""
        if is_url(spec):
            return cls.from_url(spec, **kw)
        return cls.from_path(spec, **kw)

    # ---- location ------------------------------------------------------- #
    @property
    def is_remote(self) -> bool:
        return self.url is not None

    @property
    def root(self) -> Path:
        """The local directory of the code, cloning it first if necessary."""
        if self._path is None:
            self._path = Path(tempfile.mkdtemp(prefix=f"rse-{self.name}-")) / self.name
        if self.url is not None and not self._path.exists():
            self._clone()
        if not self._path.is_dir():
            raise NotADirectoryError(f"{self._path} is not a directory")
        return self._path

    def _clone(self) -> None:
        cmd = ["git", "clone", "--depth", "1"]
        if self.ref:
            cmd += ["--branch", self.ref]
        cmd += [self.url, str(self._path)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    def output_path(self, name: str) -> Path:
        """Where an artefact such as ``inspection.yaml`` belongs for this target."""
        return self.root / name

    def iter_python_files(self) -> Iterator[Path]:
        """Every ``*.py`` under the root, skipping caches, venvs and test dirs."""
        return iter(sorted(_iter_python_files(self.root)))

    # ---- shared, cached views ------------------------------------------ #
    def decorated(self) -> List[DecoratorInfo]:
        """Decorated functions, found by importing the code (cached)."""
        if self._decorated is None:
            self._decorated = (discover_many(self.modules) if self.modules
                                 else discover_path(self.root))
        return list(self._decorated)

    def static_scan(self):
        """The AST scan of every function -- no import, no execution (cached)."""
        if self._scan is None:
            from ..scan import scan_path
            self._scan = scan_path(self.root)
        return self._scan

    def refresh(self) -> None:
        """Forget cached views, e.g. after the code was edited."""
        self._decorated = None
        self._scan = None

    def __repr__(self) -> str:
        where = self.url if self.url and self._path is None else self._path
        return f"TargetProject({self.name!r}, {where})"


def _module_dir(module: str) -> Path:
    """The directory holding ``module``: the package itself, or a module's folder."""
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None:
        raise ModuleNotFoundError(f"cannot locate module {module!r}")
    origin = Path(spec.origin)
    return origin.parent


def is_url(spec: str) -> bool:
    return bool(_URL_RE.match(spec))


def _repo_name(url: Optional[str]) -> str:
    tail = (url or "target").rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return tail[:-4] if tail.endswith(".git") else tail
