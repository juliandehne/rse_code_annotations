"""Command-line entry point.

After ``pip install`` the runner is invoked with ``python -m rse_annotations.cli``.
This needs nothing on your PATH -- the interpreter finds the installed package via
``site-packages``. (A ``rse-annotations`` console script is also installed by the
``[project.scripts]`` entry point, but using it as a bare command requires Python's
``Scripts`` dir on PATH, so the docs use the ``python -m`` form.)

Subcommands::

    python -m rse_annotations.cli kinds                    # the annotation types you can apply
    python -m rse_annotations.cli list mypkg --path src     # inventory EXISTING annotations in a target
    python -m rse_annotations.cli run  mypkg --path src     # full checks + formula inference + Fable

Examples::

    python -m rse_annotations.cli list compute_icr krippendorff_reference --path src
    python -m rse_annotations.cli run  examples.sample_pipeline
    python -m rse_annotations.cli run  mypkg --json
    python -m rse_annotations.cli run  mypkg --no-stubs     # skip Fable entirely

The target library is not installed; it is simply *added to the path* and imported
for inspection. The current working directory is on ``sys.path`` automatically, so
you can run from your project root and name top-level modules directly. Use
``--path DIR`` (repeatable) to add further source roots (e.g. ``--path src``).
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from typing import Callable, Dict, List, Optional

from .discovery import discover_many
from .registry import KIND_HELP, KINDS
from .runner import Runner, render_json, render_text


def _prepare_sys_path(paths: Optional[List[str]]) -> None:
    """Prepend the cwd and any ``--path`` dirs to ``sys.path`` for imports."""
    roots = [os.getcwd()] + list(paths or [])
    for root in reversed(roots):
        abs_root = os.path.abspath(root)
        if abs_root not in sys.path:
            sys.path.insert(0, abs_root)


def _load_fixtures(dotted: Optional[str]) -> Dict[str, Callable]:
    """Load a fixtures mapping from ``module:attribute`` (a dict of qualname->fixture)."""
    if not dotted:
        return {}
    mod_name, _, attr = dotted.partition(":")
    if not attr:
        raise SystemExit(f"--fixtures must be 'module:attribute', got {dotted!r}")
    module = importlib.import_module(mod_name)
    fixtures = getattr(module, attr)
    if not isinstance(fixtures, dict):
        raise SystemExit(f"{dotted} is not a dict of fixtures")
    return fixtures


# --------------------------------------------------------------------------- #
# Subcommand: kinds -- the menu of annotations a user can choose to apply
# --------------------------------------------------------------------------- #

def _cmd_kinds() -> int:
    lines = ["rse_code_annotations -- annotation kinds you can apply:", ""]
    for kind in KINDS:
        lines.append(f"  @{kind}")
        lines.append(f"      {KIND_HELP[kind]}")
        lines.append("")
    lines.append("Import them from the installed library and decorate your functions:")
    lines.append("    from rse_annotations import functional, mapping, data_input, data_output")
    lines.append("")
    lines.append("Then inventory them with:   python -m rse_annotations.cli list <your-module> --path <src>")
    lines.append("Or run the full checks with: python -m rse_annotations.cli run  <your-module> --path <src>")
    print("\n".join(lines))
    return 0


# --------------------------------------------------------------------------- #
# Subcommand: list -- investigate a target for EXISTING annotations
# --------------------------------------------------------------------------- #

def _cmd_list(targets: List[str], paths: Optional[List[str]]) -> int:
    _prepare_sys_path(paths)
    infos = discover_many(targets)
    if not infos:
        print(f"No existing annotations found in: {', '.join(targets)}")
        print("(Import rse_annotations and decorate functions; see `python -m rse_annotations.cli kinds`.)")
        return 0

    print(f"Existing annotations in {', '.join(targets)} -- {len(infos)} found:\n")
    for kind in KINDS:
        of_kind = [i for i in infos if i.kind == kind]
        if not of_kind:
            continue
        print(f"@{kind}  ({len(of_kind)})")
        for info in of_kind:
            print(f"  - {info.qualname:<28} {info.location}")
        print()
    return 0


# --------------------------------------------------------------------------- #
# Subcommand: run -- full checks
# --------------------------------------------------------------------------- #

def _cmd_run(args: argparse.Namespace) -> int:
    _prepare_sys_path(args.path)
    fixtures = _load_fixtures(args.fixtures)
    runner = Runner(
        args.target,
        fixtures=fixtures,
        generate_stubs=not args.no_stubs,
        probe=not args.no_probe,
        effort=args.effort,
        infer_formulas=not args.no_formulas,
    )
    report = runner.run()
    if args.json:
        print(render_json(report))
    else:
        print(render_text(report, show_snippets=not args.no_snippets))
    return 0 if report.ok else 1


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rse_annotations.cli", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("kinds", help="list the annotation kinds you can apply")

    lst = sub.add_parser("list", help="inventory existing annotations in target(s)")
    lst.add_argument("target", nargs="+",
                     help="one or more importable dotted paths, e.g. compute_icr")
    lst.add_argument("--path", action="append", metavar="DIR",
                     help="extra source root(s) to add to sys.path (repeatable)")

    run = sub.add_parser("run", help="run checks against target package(s)/module(s)")
    run.add_argument("target", nargs="+",
                     help="one or more importable dotted paths, e.g. compute_icr")
    run.add_argument("--path", action="append", metavar="DIR",
                     help="extra source root(s) to add to sys.path (repeatable)")
    run.add_argument("--json", action="store_true", help="emit JSON instead of text")
    run.add_argument("--no-stubs", action="store_true",
                     help="do not call Fable; snippet-only functional review")
    run.add_argument("--no-probe", action="store_true",
                     help="skip the Fable probe call (assume available if key present)")
    run.add_argument("--effort", default="medium",
                     choices=["low", "medium", "high", "xhigh", "max"],
                     help="Fable reasoning effort for stub generation")
    run.add_argument("--fixtures", default=None,
                     help="module:attribute pointing at a dict of I/O fixtures")
    run.add_argument("--no-snippets", action="store_true",
                     help="omit full source snippets from text output")
    run.add_argument("--no-formulas", action="store_true",
                     help="skip formula inference for @functional code")

    args = parser.parse_args(argv)

    if args.command == "kinds":
        return _cmd_kinds()
    if args.command == "list":
        return _cmd_list(args.target, args.path)
    if args.command == "run":
        return _cmd_run(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
