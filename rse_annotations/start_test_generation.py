"""Test generation: A plugin writes test scaffolds for the code it cares about.

Start it directly with ``python -m rse_annotations.start_test_generation [path]``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Union

if not __package__:  # started as a file (IDE "Run" button): make the package importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rse_annotations.core.plugin import Mode, Plugin  # noqa: E402
from rse_annotations.manager import Manager, parse_start_args  # noqa: E402


def test_generation(manager: Manager, plugin: Union[str, Plugin, None] = None) -> int:
    """A plugin writes test scaffolds for the code it cares about.

    Args:
        plugin: A plugin or its name (default: the only one offering this, or you are asked).
    """
    chosen, code = manager.plugin_for(Mode.GENERATE_TESTS, plugin)
    if chosen is None:
        return code
    chosen.generate_tests(manager.target, output_fn=manager.output_fn)
    return 0


def main(argv=None, *, input_fn=input, output_fn=print) -> int:
    args = parse_start_args("Test generation, started directly (without the mode menu).", argv)

    manager = Manager.for_path(args.path, input_fn=input_fn, output_fn=output_fn)
    if manager is None:  # the path is not a directory
        return 2
    return test_generation(manager, args.plugin)


if __name__ == "__main__":
    sys.exit(main())
