"""Command-line entry point -- an interactive, two-option tool.

Invoke with ``python -m rse_annotations.cli`` (needs nothing on your PATH). Point it
at a directory of code that uses the four annotations; if you give no path, the
current directory is used::

    python -m rse_annotations.cli                 # scan the current directory
    python -m rse_annotations.cli path/to/src     # scan a specific directory

It discovers the annotations, then offers exactly two actions:

    1) Inspect @functional annotations -- step through each one, see its source and
       inferred formula, and accept or decline it. Verdicts are written to
       ``<path>/inspection.yaml``. The point is to make it easy to *review generated
       code* for mathematical correctness.

    2) Generate unit-test stubs -- for every annotation, emit a pattern-based
       ``pytest`` scaffold (no LLM required) under ``<path>/tests/``.

Pass ``--inspect`` or ``--stubs`` to pick an action directly and skip the menu.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, List, Optional

from .discovery import discover_path
from .inspection import run_inspection
from .registry import AnnotationInfo, KINDS
from .stubs import generate_stub_files


def _summarise(infos: List[AnnotationInfo]) -> str:
    counts = {k: sum(1 for i in infos if i.kind == k) for k in KINDS}
    parts = [f"{n} @{k}" for k, n in counts.items() if n]
    return ", ".join(parts) if parts else "none"


def _choose(input_fn: Callable[[str], str], output_fn: Callable[[str], None]) -> Optional[str]:
    """Show the two-option menu and return 'inspect', 'stubs', or None to quit."""
    output_fn("")
    output_fn("Choose an action:")
    output_fn("  1) Inspect @functional annotations   (accept/decline each -> inspection.yaml)")
    output_fn("  2) Generate unit-test stubs for all annotations   (-> tests/)")
    while True:
        try:
            choice = input_fn("> ").strip().lower()
        except EOFError:
            return None
        if choice in ("1", "inspect", "i"):
            return "inspect"
        if choice in ("2", "stubs", "s"):
            return "stubs"
        if choice in ("q", "quit", "", "exit"):
            return None
        output_fn("  please enter 1 or 2 (or q to quit)")


def _do_inspect(infos, root: Path, input_fn, output_fn) -> int:
    out_path = root / "inspection.yaml"
    run_inspection(infos, out_path, input_fn=input_fn, output_fn=output_fn)
    return 0


def _do_stubs(infos, root: Path, output_fn) -> int:
    out_dir = root / "tests"
    files = generate_stub_files(infos, out_dir)
    if not files:
        output_fn("No annotations found; nothing to scaffold.")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for sf in files:
        sf.path.write_text(sf.content, encoding="utf-8")
        output_fn(f"  wrote {sf.path}  ({sf.stub_count} annotation(s) from {sf.source_module})")
        written += sf.stub_count
    output_fn("")
    output_fn(f"Generated {written} stub(s) across {len(files)} file(s) in {out_dir}")
    output_fn("Every test is a SKIPPED scaffold -- fill in the TODOs to make them run.")
    return 0


def main(
    argv: Optional[list] = None,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rse_annotations.cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="directory of code to scan (default: current directory)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inspect", action="store_true",
                      help="inspect @functional annotations (skip the menu)")
    mode.add_argument("--stubs", action="store_true",
                      help="generate unit-test stubs (skip the menu)")
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.is_dir():
        output_fn(f"error: {root} is not a directory")
        return 2

    infos = discover_path(root)
    output_fn(f"Scanned {root}")
    output_fn(f"Found {len(infos)} annotation(s): {_summarise(infos)}")
    if not infos:
        output_fn("Nothing to do. Decorate functions with the four annotations first:")
        output_fn("    from rse_annotations import functional, mapping, data_input, data_output")
        return 0

    if args.inspect:
        action = "inspect"
    elif args.stubs:
        action = "stubs"
    else:
        action = _choose(input_fn, output_fn)

    if action == "inspect":
        return _do_inspect(infos, root, input_fn, output_fn)
    if action == "stubs":
        return _do_stubs(infos, root, output_fn)
    output_fn("No action chosen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
