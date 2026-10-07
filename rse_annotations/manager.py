"""What every feature of the tool needs: the code to check and the plugins.

A :class:`Manager` holds the target project, the plugins, and how to talk to the user.
The program flow of each feature is in its own start file, which can also be run directly:

====================  ============================================  ====================
feature               start file                                    function
====================  ============================================  ====================
Human inspection      :mod:`rse_annotations.start_inspection`       ``human_inspection``
External review       :mod:`rse_annotations.start_review`           ``external_review``
Hazard analysis       :mod:`rse_annotations.start_analysis`         ``hazard_analysis``
Test generation       :mod:`rse_annotations.start_test_generation`  ``test_generation``
====================  ============================================  ====================

Each of them takes a manager::

    manager = Manager.for_path("src")      # 1. find the code to check
    human_inspection(manager)              # 2. run one feature (returns an exit code)

The two reviews and the test generation are done by **one** plugin (you are asked which
if several offer the feature, see :meth:`Manager.plugin_for`); the hazard analysis runs
**every** selected plugin. Every feature returns a process exit code: 0 = fine,
1 = findings / not possible here, 2 = wrong input.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple, Union

from .core.audit import Audit
from .core.catalog import PluginCatalog
from .core.plugin import Mode, Plugin
from .core.target import TargetProject, is_url
from .decorators.markers import REVIEW_CONCERNS
from .reporting import OutputFormat, write_coverage_report

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


class Manager:
    """One target project, its plugins, and how to talk to the user.

    Args:
        target: The project under audit.
        catalog: Where plugins come from; defaults to the shipped ones + installed ones.
        plugins: Explicit (e.g. configured) plugin instances; they replace the
            catalog's default instances.
        input_fn / output_fn: How the interactive features talk to the user
            (replaced in the tests).
    """

    def __init__(self, target: TargetProject, *, catalog: Optional[PluginCatalog] = None,
                 plugins: Optional[List[Plugin]] = None, input_fn: InputFn = input,
                 output_fn: OutputFn = print) -> None:
        self.target = target
        self.audit = Audit(target, catalog=catalog, plugins=plugins)
        self.catalog = self.audit.catalog
        self.input_fn = input_fn
        self.output_fn = output_fn

    @classmethod
    def for_path(cls, spec: str, *, output_fn: OutputFn = print, **kwargs) -> Optional["Manager"]:
        """A manager for a directory or a git URL; None (after a message) if it is neither."""
        if is_url(spec):
            target = TargetProject.from_url(spec)
        else:
            path = Path(spec).resolve()
            if not path.is_dir():
                output_fn(f"error: {path} is not a directory")
                return None
            target = TargetProject.from_path(path)
        return cls(target, output_fn=output_fn, **kwargs)

    # ---- reports that need no plugin ------------------------------------ #
    def summary(self) -> int:
        """Print what the static scan found (no import); return the decorator count."""
        counts = self.target.static_scan().counts_by_kind()
        total = sum(counts.values())
        parts = [f"{counts[k]} @{k}" for k in REVIEW_CONCERNS if counts.get(k)]
        self.output_fn(f"Scanned {self.target.root}")
        self.output_fn(f"Found {total} decorated function(s): "
                       f"{', '.join(parts) if parts else 'none'}")
        return total

    def coverage(self) -> int:
        """Static decorator coverage + candidates (-> decorator_coverage.md)."""
        return write_coverage_report(self.target, self.output_fn)

    def suggest_decorators(self) -> int:
        """Nothing is decorated yet: say so and show where decorators would go."""
        return suggest_decorators(self.target, self.output_fn)

    # ---- which plugin does the work? ------------------------------------ #
    def plugin_for(self, mode: Mode,
                   plugin: Union[str, Plugin, None]) -> Tuple[Optional[Plugin], int]:
        """The plugin to use for ``mode``, or ``(None, exit code)`` if there is none.

        ``plugin`` is an instance, a name, or None -- then the only plugin offering
        the mode is taken, or the user is asked which.
        """
        label = mode.label
        if isinstance(plugin, Plugin):
            chosen = plugin
        elif plugin:
            if plugin not in self.catalog:
                self.output_fn(f"error: unknown plugin {plugin!r}")
                return None, 2
            if not self.catalog.get(plugin).supports(mode):
                self.output_fn(f"error: {plugin} does not offer {label.lower()}")
                return None, 2
            chosen = self.audit.plugin(plugin)
        else:
            offering = self.catalog.for_mode(mode)
            if not offering:
                self.output_fn(f"No plugin offers {label.lower()}.")
                return None, 1
            name = offering[0].name
            if len(offering) > 1:
                name = choose([(c.name, f"{c.name} -- {c.description}") for c in offering],
                              self.input_fn, self.output_fn, f"{label} with which plugin?")
                if name is None:
                    self.output_fn("No plugin chosen.")
                    return None, 0
            chosen = self.audit.plugin(name)
        if not chosen.available():
            self.output_fn(f"{chosen.name}: {chosen.unavailable_reason()}")
            return None, 1
        return chosen, 0


def choose(options: Sequence[Tuple[str, str]], input_fn: InputFn, output_fn: OutputFn,
           title: str) -> Optional[str]:
    """Numbered menu over ``(key, label)`` pairs; returns a key, or None to quit."""
    output_fn("")
    output_fn(title)
    for i, (_, label) in enumerate(options, start=1):
        output_fn(f"  {i}) {label}")
    keys = {str(i): key for i, (key, _) in enumerate(options, start=1)}
    keys.update({key: key for key, _ in options})
    while True:
        try:
            choice = input_fn("> ").strip().lower()
        except EOFError:
            return None
        if choice in keys:
            return keys[choice]
        if choice in ("q", "quit", "", "exit"):
            return None
        output_fn(f"  please enter 1-{len(options)} (or q to quit)")


def list_plugins(catalog: PluginCatalog, output_fn: OutputFn = print) -> int:
    """Print the plugins and the modes they offer."""
    for cls in catalog.classes():
        state = cls.when if cls().available() else f"{cls.when}, not available"
        tier = getattr(cls, "tier", None)
        if tier:
            state += f", tier {tier}"
        modes = "/".join(m.replace(Mode.GENERATE_TESTS, "tests")
                         for m in cls.modes())
        output_fn(f"  {cls.name:<24} [{state}] ({modes})  {cls.description}")
    for ep, err in catalog.errors:
        output_fn(f"  (plugin {ep} failed to load: {err})")
    return 0


def suggest_decorators(target: TargetProject, output_fn: OutputFn = print) -> int:
    """Nothing is decorated yet: say so and show where decorators would go."""
    output_fn("No decorators yet. Here is where they would go (coverage scan of the same tree):")
    return write_coverage_report(target, output_fn)


# --------------------------------------------------------------------------- #
# Command-line plumbing shared by cli.py and the start files
# --------------------------------------------------------------------------- #

def add_path_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", nargs="?", default=".",
                        help="directory or git URL of code to check (default: current directory)")


def add_plugin_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--plugin", default=None,
                        help="the plugin to use for a review or the test generation "
                             "(default: the only one, or you are asked)")
    parser.add_argument("--only", default=None,
                        help="hazard analysis: comma-separated plugin names (default: all)")


def add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", type=OutputFormat, choices=list(OutputFormat),
                        default=OutputFormat.TEXT,
                        help="hazard analysis: output format (default: text)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="hazard analysis: also show info findings")


def plugin_names(only: Optional[str]) -> Optional[List[str]]:
    """``"a, b"`` (the value of ``--only``) -> ``["a", "b"]``; None stays None (= all)."""
    return [n.strip() for n in only.split(",")] if only else None


def parse_start_args(description: str, argv: Optional[list] = None) -> argparse.Namespace:
    """The command line of a start file: ``path``, ``--plugin``, ``--only``, ``--format``, ``-v``."""
    parser = argparse.ArgumentParser(description=description)
    add_path_arg(parser)
    add_plugin_args(parser)
    add_output_args(parser)
    return parser.parse_args(argv)
