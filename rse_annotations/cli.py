"""Command-line entry point.

After ``pip install rse-code-annotations`` this is available as the
``rse-annotations`` console command (and as ``python -m rse_annotations.cli``).

Examples::

    rse-annotations run examples.sample_pipeline
    rse-annotations run compute_icr krippendorff_reference --path src
    rse-annotations run mypkg --json
    rse-annotations run mypkg --no-stubs        # skip Fable entirely
    rse-annotations run mypkg --no-probe        # assume Fable if key set

The current working directory is added to ``sys.path`` automatically, so you can
run the command from your project root and name top-level modules directly. Use
``--path DIR`` (repeatable) to add further source roots (e.g. ``--path src``).
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from typing import Callable, Dict, List, Optional

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


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="rse_annotations", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

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

    if args.command == "run":
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

    return 2


if __name__ == "__main__":
    sys.exit(main())
