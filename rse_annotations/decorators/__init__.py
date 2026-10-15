"""The concerns: one sub-package per decorator, found automatically.

A new concern is a new folder ``decorators/<name>/__init__.py`` that defines
``CONCERN = Concern("<name>", help, detect, ...)``. Nothing else needs registering.
"""
import importlib
import pkgutil

from ._base import Concern, FunctionView

#: name -> Concern, in folder order.
CONCERNS = {}
for _m in pkgutil.iter_modules(__path__):
    if _m.ispkg:
        _c = importlib.import_module(f"{__name__}.{_m.name}").CONCERN
        CONCERNS[_c.name] = _c
        globals()[_c.name] = _c

__all__ = ["CONCERNS", "Concern", "FunctionView", *CONCERNS]
