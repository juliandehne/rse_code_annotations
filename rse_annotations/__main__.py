"""``python -m rse_annotations [path]`` -- the general entry point (see :mod:`.cli`)."""

import sys

from .cli import main

sys.exit(main())
