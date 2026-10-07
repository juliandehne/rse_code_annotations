"""Command-line entry points.

**General entry point** -- ``python -m rse_annotations [path]``. Pick a mode, and the
tool delegates to every plugin that offers it::

    1) Human inspection   -- a person reviews flagged code, verdicts are recorded
    2) Hazard analysis    -- every plugin examines the code and reports findings
    3) Test generation    -- plugins write test scaffolds
    4) External review    -- an outside reviewer inspects the marked code; writes a protocol

If more than one plugin offers the chosen mode (inspection, test generation, review) you are
asked which; ``--plugin NAME`` picks directly. Skip the menu with ``--inspect``,
``--analyze``, ``--tests`` or ``--review``::

    python -m rse_annotations src --analyze --only human_code_inspection -v
    python -m rse_annotations src --analyze --format json > audit.json
    python -m rse_annotations --list
    python -m rse_annotations src --coverage     # static; never imports the code
    python -m rse_annotations src --review       # interactive, static; writes review_protocol.yaml

The program flow itself -- what each mode does -- is in the start file of that mode
(:mod:`rse_annotations.start_inspection`, ``.start_review``, ``.start_analysis``,
``.start_test_generation``), each of which can also be run directly; this module only
parses the command line, shows the menus and calls them (:func:`run_mode`).

**Per-plugin entry point** -- ``python -m rse_annotations.plugins.hazards.<name>``
offers only that plugin's modes (plus any extra actions it adds, e.g. the coverage
report of ``human_code_inspection``). Plugins build it with :func:`plugin_main`.

The path may also be a git URL; it is shallow-cloned into a temporary directory.
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Dict, Iterable, Optional, Tuple, Union

from .core.catalog import PluginCatalog, default_catalog
from .core.plugin import MODES, Mode, Plugin
from .core.target import TargetProject
from .reporting import OutputFormat
from .manager import (InputFn, Manager, OutputFn, add_output_args, add_path_arg,
                      add_plugin_args, choose, list_plugins, plugin_names)
from .start_analysis import hazard_analysis
from .start_inspection import human_inspection
from .start_review import external_review
from .start_test_generation import test_generation

#: An extra per-plugin action: ``(menu label, fn(plugin, target, output_fn) -> exit code)``.
ExtraAction = Tuple[str, Callable[[Plugin, TargetProject, OutputFn], int]]

_MODE_FLAGS = {"inspect": Mode.INSPECT, "analyze": Mode.ANALYZE, "tests": Mode.GENERATE_TESTS,
               "review": Mode.REVIEW}
_MODE_HINTS = {
    Mode.INSPECT: "a person reviews flagged code; verdicts are recorded",
    Mode.ANALYZE: "every plugin examines the code and reports findings",
    Mode.GENERATE_TESTS: "write test scaffolds",
    Mode.REVIEW: "an outside reviewer inspects the marked code; writes a protocol",
}


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def _add_mode_args(group) -> None:
    group.add_argument("--inspect", action="store_true", help="human inspection (skip the menu)")
    group.add_argument("--analyze", action="store_true", help="hazard analysis (skip the menu)")
    group.add_argument("--tests", "--stubs", dest="tests", action="store_true",
                       help="test generation (skip the menu)")
    group.add_argument("--review", action="store_true",
                       help="external review (skip the menu; -> review_protocol.yaml)")


def _mode_from_args(args) -> Optional[Mode]:
    for flag, mode in _MODE_FLAGS.items():
        if getattr(args, flag, False):
            return mode
    return None


def run_mode(manager: Manager, mode: Mode, plugin: Union[str, Plugin, None] = None, *,
             only: Optional[Iterable[str]] = None, fmt: OutputFormat = OutputFormat.TEXT,
             verbose: bool = False) -> int:
    """Call the feature named by ``mode``."""
    if mode is Mode.INSPECT:
        return human_inspection(manager, plugin)
    if mode is Mode.REVIEW:
        return external_review(manager, plugin)
    if mode is Mode.GENERATE_TESTS:
        return test_generation(manager, plugin)
    if isinstance(plugin, Plugin):
        only = [plugin.name]
    elif plugin:
        only = [plugin]
    return hazard_analysis(manager, only, fmt=fmt, verbose=verbose)


# --------------------------------------------------------------------------- #
# General entry point
# --------------------------------------------------------------------------- #

def main(argv: Optional[list] = None, *, input_fn: InputFn = input,
         output_fn: OutputFn = print, catalog: Optional[PluginCatalog] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rse_annotations", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    add_path_arg(parser)
    mode = parser.add_mutually_exclusive_group()
    _add_mode_args(mode)
    mode.add_argument("--list", "--list-plugins", dest="list", action="store_true",
                      help="list the plugins and the modes they offer, then exit")
    mode.add_argument("--coverage", action="store_true",
                      help="static decorator coverage + candidates (-> decorator_coverage.md)")
    add_plugin_args(parser)
    add_output_args(parser)
    args = parser.parse_args(argv)

    catalog = catalog if catalog is not None else default_catalog()
    if args.list:
        return list_plugins(catalog, output_fn)

    manager = Manager.for_path(args.path, catalog=catalog, input_fn=input_fn,
                               output_fn=output_fn)
    if manager is None:
        return 2
    if args.coverage:
        return manager.coverage()

    chosen = _mode_from_args(args)
    if chosen is None:
        if not manager.summary():
            return manager.suggest_decorators()
        options = [(m, f"{m.label:<17} -- {_MODE_HINTS[m]}")
                   for m in MODES if catalog.for_mode(m)]
        chosen = choose(options, input_fn, output_fn, "Choose a mode:")
        if chosen is None:
            output_fn("No mode chosen.")
            return 0

    return run_mode(manager, chosen, args.plugin, only=plugin_names(args.only),
                    fmt=args.format, verbose=args.verbose)


# --------------------------------------------------------------------------- #
# Per-plugin entry point
# --------------------------------------------------------------------------- #

def plugin_main(plugin_factory: Callable[[], Plugin], argv: Optional[list] = None, *,
                input_fn: InputFn = input, output_fn: OutputFn = print,
                extra_actions: Optional[Dict[str, ExtraAction]] = None,
                before_menu: Optional[Callable[[Plugin, TargetProject, OutputFn], Optional[int]]] = None,
                ) -> int:
    """The ``__main__`` of one plugin: its own modes plus ``extra_actions``.

    Args:
        plugin_factory: Builds the plugin (usually its class).
        extra_actions: ``{flag: (menu label, fn(plugin, target, output_fn) -> int)}``;
            each becomes a ``--flag`` and a menu entry.
        before_menu: Called before the menu is shown; a non-None return ends the run
            with that exit code (e.g. "nothing decorated yet").
    """
    plugin = plugin_factory()
    extra_actions = dict(extra_actions or {})
    parser = argparse.ArgumentParser(prog=f"python -m ...{plugin.name}",
                                     description=type(plugin).__doc__)
    add_path_arg(parser)
    group = parser.add_mutually_exclusive_group()
    _add_mode_args(group)
    for flag, (label, _) in extra_actions.items():
        group.add_argument(f"--{flag}", dest=f"extra_{flag}", action="store_true", help=label)
    add_output_args(parser)
    args = parser.parse_args(argv)

    manager = Manager.for_path(args.path, catalog=PluginCatalog(), plugins=[plugin],
                               input_fn=input_fn, output_fn=output_fn)
    if manager is None:
        return 2
    target = manager.target

    chosen = _mode_from_args(args) or next(
        (f for f in extra_actions if getattr(args, f"extra_{f}")), None)
    if chosen is None:
        manager.summary()
        if before_menu is not None:
            code = before_menu(plugin, target, output_fn)
            if code is not None:
                return code
        options = [(m, m.label) for m in MODES if plugin.supports(m)]
        options += [(flag, label) for flag, (label, _) in extra_actions.items()]
        chosen = choose(options, input_fn, output_fn, f"{plugin.name}: choose an action:")
        if chosen is None:
            output_fn("No action chosen.")
            return 0

    if chosen in extra_actions:
        return extra_actions[chosen][1](plugin, target, output_fn)
    if not plugin.supports(chosen):
        output_fn(f"error: {plugin.name} does not offer {chosen.label.lower()}")
        return 2
    return run_mode(manager, chosen, plugin, fmt=args.format, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
