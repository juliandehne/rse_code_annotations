"""``python -m rse_annotations.plugins.hazards.human_code_inspection [path]``

The plugin's own entry point: human inspection, hazard analysis, test generation,
plus the static annotation-coverage report (``--coverage``, never imports the target).
"""

from __future__ import annotations

import sys
from typing import Optional

from ....cli import plugin_main
from ....reporting import write_coverage_report
from .plugin import HumanCodeInspection


def _coverage(plugin, target, output_fn) -> int:
    return write_coverage_report(target, output_fn)


def _nothing_annotated(plugin, target, output_fn) -> Optional[int]:
    if target.static_scan().annotated:
        return None
    output_fn("No annotations yet. Here is where they would go (coverage scan of the same tree):")
    return write_coverage_report(target, output_fn)


EXTRA_ACTIONS = {"coverage": ("Annotation coverage + candidates  (-> annotation_coverage.md)",
                              _coverage)}


def main(argv=None, **io) -> int:
    return plugin_main(HumanCodeInspection, argv, extra_actions=EXTRA_ACTIONS,
                       before_menu=_nothing_annotated, **io)


if __name__ == "__main__":
    sys.exit(main())
