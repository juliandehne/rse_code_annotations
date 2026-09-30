"""Command-line entry points.

**General entry point** -- ``python -m rse_annotations [path]``. Pick a mode, and the
tool delegates to every plugin that offers it::

    1) Human inspection   -- a person reviews flagged code, verdicts are recorded
    2) Hazard analysis    -- every plugin examines the code and reports findings
    3) Test generation    -- plugins write test scaffolds

If more than one plugin offers the chosen mode (inspection, test generation) you are
asked which; ``--plugin NAME`` picks directly. Skip the menu with ``--inspect``,
``--analyze`` or ``--tests``::

    python -m rse_annotations src --analyze --only human_code_inspection -v
    python -m rse_annotations src --analyze --format json > audit.json
    python -m rse_annotations --list
    python -m rse_annotations src --coverage     # static; never imports the code

**Per-plugin entry point** -- ``python -m rse_annotations.plugins.hazards.<name>``
offers only that plugin's modes (plus any extra actions it adds, e.g. the coverage
report of ``human_code_inspection``). Plugins build it with :func:`plugin_main`.

The path may also be a git URL; it is shallow-cloned into a temporary directory.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .annotations.registry import KINDS
from .core.audit import Audit
from .core.catalog import PluginCatalog, default_catalog
from .core.plugin import MODE_LABELS, MODES, Plugin
from .core.target import TargetProject, is_url
from .reporting import RENDERERS, TextRenderer, write_coverage_report

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]
#: An extra per-plugin action: ``(menu label, fn(plugin, target, output_fn) -> exit code)``.
ExtraAction = Tuple[str, Callable[[Plugin, TargetProject, OutputFn], int]]

_MODE_FLAGS = {"inspect": "inspect", "analyze": "analyze", "tests": "generate_tests"}
_MODE_HINTS = {
    "inspect": "a person reviews flagged code; verdicts are recorded",
    "analyze": "every plugin examines the code and reports findings",
    "generate_tests": "write test scaffolds",
}


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def _target(spec: str, output_fn: OutputFn) -> Optional[TargetProject]:
    if is_url(spec):
        return TargetProject.from_url(spec)
    path = Path(spec).resolve()
    if not path.is_dir():
        output_fn(f"error: {path} is not a directory")
        return None
    return TargetProject.from_path(path)


def _header(target: TargetProject, output_fn: OutputFn) -> int:
    """Print what the static scan found (no import); return the annotation count."""
    counts = target.static_scan().counts_by_kind()
    total = sum(counts.values())
    parts = [f"{counts[k]} @{k}" for k in KINDS if counts.get(k)]
    output_fn(f"Scanned {target.root}")
    output_fn(f"Found {total} annotation(s): {', '.join(parts) if parts else 'none'}")
    return total


def _menu(options: Sequence[Tuple[str, str]], input_fn: InputFn, output_fn: OutputFn,
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


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=sorted(RENDERERS), default="text",
                        help="with --analyze: output format (default: text)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="with --analyze: also show info findings")


def _add_mode_args(group) -> None:
    group.add_argument("--inspect", action="store_true", help="human inspection (skip the menu)")
    group.add_argument("--analyze", action="store_true", help="hazard analysis (skip the menu)")
    group.add_argument("--tests", "--stubs", dest="tests", action="store_true",
                       help="test generation (skip the menu)")


def _mode_from_args(args) -> Optional[str]:
    for flag, mode in _MODE_FLAGS.items():
        if getattr(args, flag, False):
            return mode
    return None


def _analyze(audit: Audit, plugins: List[Plugin], fmt: str, verbose: bool,
             output_fn: OutputFn) -> int:
    results = [audit.run_one(p) for p in plugins]
    renderer = TextRenderer(verbose=verbose) if fmt == "text" else RENDERERS[fmt]()
    output_fn(renderer.render_results(results))
    return 0 if all(r.ok for r in results) else 1


def _run(plugin: Plugin, mode: str, target: TargetProject, input_fn: InputFn,
         output_fn: OutputFn) -> int:
    if not plugin.available():
        output_fn(f"{plugin.name}: {plugin.unavailable_reason()}")
        return 1
    if mode == "inspect":
        plugin.inspect(target, input_fn=input_fn, output_fn=output_fn)
    else:
        plugin.generate_tests(target, output_fn=output_fn)
    return 0


def list_plugins(catalog: PluginCatalog, output_fn: OutputFn) -> int:
    for cls in catalog.classes():
        state = cls.when if cls().available() else f"{cls.when}, not available"
        tier = getattr(cls, "tier", None)
        if tier:
            state += f", tier {tier}"
        modes = "/".join(m.replace("generate_tests", "tests") for m in cls.modes())
        output_fn(f"  {cls.name:<24} [{state}] ({modes})  {cls.description}")
    for ep, err in catalog.errors:
        output_fn(f"  (plugin {ep} failed to load: {err})")
    return 0


# --------------------------------------------------------------------------- #
# General entry point
# --------------------------------------------------------------------------- #

def main(argv: Optional[list] = None, *, input_fn: InputFn = input,
         output_fn: OutputFn = print, catalog: Optional[PluginCatalog] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rse_annotations", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", default=".",
                        help="directory or git URL of code to check (default: current directory)")
    mode = parser.add_mutually_exclusive_group()
    _add_mode_args(mode)
    mode.add_argument("--list", "--list-plugins", dest="list", action="store_true",
                      help="list the plugins and the modes they offer, then exit")
    mode.add_argument("--coverage", action="store_true",
                      help="static annotation coverage + candidates (-> annotation_coverage.md)")
    parser.add_argument("--plugin", default=None,
                        help="the plugin to use for --inspect / --tests")
    parser.add_argument("--only", default=None,
                        help="with --analyze: comma-separated plugin names (default: all)")
    _add_output_args(parser)
    args = parser.parse_args(argv)

    catalog = catalog if catalog is not None else default_catalog()
    if args.list:
        return list_plugins(catalog, output_fn)

    target = _target(args.path, output_fn)
    if target is None:
        return 2
    audit = Audit(target, catalog=catalog)
    if args.coverage:
        return write_coverage_report(target, output_fn)

    chosen = _mode_from_args(args)
    if chosen is None:
        if not _header(target, output_fn):
            output_fn("No annotations yet. Here is where they would go "
                      "(coverage scan of the same tree):")
            return write_coverage_report(target, output_fn)
        options = [(m, f"{MODE_LABELS[m]:<17} -- {_MODE_HINTS[m]}")
                   for m in ("inspect", "analyze", "generate_tests") if catalog.for_mode(m)]
        chosen = _menu(options, input_fn, output_fn, "Choose a mode:")
        if chosen is None:
            output_fn("No mode chosen.")
            return 0

    if chosen == "analyze":
        names = [n.strip() for n in args.only.split(",")] if args.only else None
        if args.plugin:
            names = [args.plugin]
        try:
            plugins = audit.select(names)
        except KeyError as exc:
            output_fn(f"error: {exc.args[0]}")
            return 2
        return _analyze(audit, plugins, args.format, args.verbose, output_fn)

    offering = [c for c in catalog.for_mode(chosen)]
    if args.plugin:
        if args.plugin not in catalog:
            output_fn(f"error: unknown plugin {args.plugin!r}")
            return 2
        cls = catalog.get(args.plugin)
        if not cls.supports(chosen):
            output_fn(f"error: {cls.name} does not offer {MODE_LABELS[chosen].lower()}")
            return 2
    elif not offering:
        output_fn(f"No plugin offers {MODE_LABELS[chosen].lower()}.")
        return 1
    elif len(offering) == 1:
        cls = offering[0]
    else:
        name = _menu([(c.name, f"{c.name} -- {c.description}") for c in offering],
                     input_fn, output_fn, f"{MODE_LABELS[chosen]} with which plugin?")
        if name is None:
            output_fn("No plugin chosen.")
            return 0
        cls = catalog.get(name)
    return _run(audit.plugin(cls.name), chosen, target, input_fn, output_fn)


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
            with that exit code (e.g. "nothing annotated yet").
    """
    plugin = plugin_factory()
    extra_actions = dict(extra_actions or {})
    parser = argparse.ArgumentParser(prog=f"python -m ...{plugin.name}",
                                     description=type(plugin).__doc__)
    parser.add_argument("path", nargs="?", default=".",
                        help="directory or git URL of code to check (default: current directory)")
    group = parser.add_mutually_exclusive_group()
    _add_mode_args(group)
    for flag, (label, _) in extra_actions.items():
        group.add_argument(f"--{flag}", dest=f"extra_{flag}", action="store_true", help=label)
    _add_output_args(parser)
    args = parser.parse_args(argv)

    target = _target(args.path, output_fn)
    if target is None:
        return 2

    chosen = _mode_from_args(args) or next(
        (f for f in extra_actions if getattr(args, f"extra_{f}")), None)
    if chosen is None:
        _header(target, output_fn)
        if before_menu is not None:
            code = before_menu(plugin, target, output_fn)
            if code is not None:
                return code
        options = [(m, MODE_LABELS[m]) for m in MODES if plugin.supports(m)]
        options += [(flag, label) for flag, (label, _) in extra_actions.items()]
        chosen = _menu(options, input_fn, output_fn, f"{plugin.name}: choose an action:")
        if chosen is None:
            output_fn("No action chosen.")
            return 0

    if chosen in extra_actions:
        return extra_actions[chosen][1](plugin, target, output_fn)
    if not plugin.supports(chosen):
        output_fn(f"error: {plugin.name} does not offer {MODE_LABELS[chosen].lower()}")
        return 2
    if chosen == "analyze":
        return _analyze(Audit(target, catalog=PluginCatalog(), plugins=[plugin]), [plugin],
                        args.format, args.verbose, output_fn)
    return _run(plugin, chosen, target, input_fn, output_fn)


if __name__ == "__main__":
    sys.exit(main())
