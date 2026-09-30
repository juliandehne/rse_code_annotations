"""Everything the tool can check, as plugins. Today there is one category, ``hazards``."""

from __future__ import annotations

from .hazards import HAZARD_PLUGINS

#: Shipped with the package, in listing order.
BUILTIN_PLUGINS = HAZARD_PLUGINS

__all__ = ["BUILTIN_PLUGINS", "HAZARD_PLUGINS"]
