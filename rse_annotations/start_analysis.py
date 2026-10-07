"""Hazard analysis: Every selected plugin examines the code; the findings are printed.

Start it directly with ``python -m rse_annotations.start_analysis [path]``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Optional

if not __package__:  # started as a file (IDE "Run" button): make the package importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rse_annotations.manager import Manager, parse_start_args, plugin_names  # noqa: E402
from rse_annotations.reporting import RENDERERS, OutputFormat, TextRenderer  # noqa: E402


def hazard_analysis(manager: Manager, only: Optional[Iterable[str]] = None, *,
                    fmt: OutputFormat = OutputFormat.TEXT, verbose: bool = False) -> int:
    """Every selected plugin examines the code; the findings are printed.

    Args:
        only: Plugin names to run (default: all that offer an analysis).
        fmt: The :class:`~rse_annotations.reporting.OutputFormat` of the report.
        verbose: In the text format, also show info findings.
    """
    try:
        plugins = manager.audit.select(only)
    except KeyError as exc:
        manager.output_fn(f"error: {exc.args[0]}")
        return 2
    results = [manager.audit.run_one(p) for p in plugins]
    renderer = TextRenderer(verbose=verbose) if fmt == OutputFormat.TEXT else RENDERERS[fmt]()
    manager.output_fn(renderer.render_results(results))
    return 0 if all(r.ok for r in results) else 1


def main(argv=None, *, input_fn=input, output_fn=print) -> int:
    args = parse_start_args("Hazard analysis, started directly (without the mode menu).", argv)

    manager = Manager.for_path(args.path, input_fn=input_fn, output_fn=output_fn)
    if manager is None:  # the path is not a directory
        return 2
    return hazard_analysis(manager, plugin_names(args.only), fmt=args.format, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
