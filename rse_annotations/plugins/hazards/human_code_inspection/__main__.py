"""``python -m rse_annotations.plugins.hazards.human_code_inspection [path]``

The plugin's own entry point: human inspection, hazard analysis, test generation,
the external review, plus the static decorator-coverage report (``--coverage``, never imports the target).
"""

from __future__ import annotations

import sys
from typing import Optional

from ....cli import plugin_main
from ....manager import suggest_decorators
from ....reporting import write_coverage_report
from .plugin import HumanCodeInspection


def _coverage(plugin, target, output_fn) -> int:
    return write_coverage_report(target, output_fn)


def _nothing_annotated(plugin, target, output_fn) -> Optional[int]:
    if target.static_scan().decorated:
        return None
    return suggest_decorators(target, output_fn)


EXTRA_ACTIONS = {"coverage": ("Decorator coverage + candidates  (-> decorator_coverage.md)",
                              _coverage)}


def main(argv=None, **io) -> int:
    return plugin_main(HumanCodeInspection, argv, extra_actions=EXTRA_ACTIONS,
                       before_menu=_nothing_annotated, **io)


if __name__ == "__main__":
    sys.exit(main())
