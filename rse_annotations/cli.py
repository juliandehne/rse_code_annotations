"""Command-line entry point.

Examples::

    python -m rse_annotations.cli run examples.sample_pipeline
    python -m rse_annotations.cli run mypkg --json
    python -m rse_annotations.cli run mypkg --no-stubs        # skip Fable entirely
    python -m rse_annotations.cli run mypkg --no-probe        # assume Fable if key set
"""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import Callable, Dict, Optional

from .runner import Runner, render_json, render_text


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

    run = sub.add_parser("run", help="run checks against a target package/module")
    run.add_argument("target", help="importable dotted path, e.g. examples.sample_pipeline")
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
