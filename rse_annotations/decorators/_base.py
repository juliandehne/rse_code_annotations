"""What every concern shares: the :class:`Concern` object and a view of a function body.

A concern is one folder under ``decorators/`` with a ``concern.py``: a subclass of
:class:`Concern` whose instance is the decorator (``@x`` or ``@x(fields=...)``; it only
marks the function) and whose ``detect`` says, from the AST alone, whether a function
looks like it carries that concern.
"""
from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, List, Optional, Set, Tuple

#: What a detector returns when it fires: (reason, confidence).
Evidence = Tuple[str, str]

# Which call names count as file I/O. Shared by the dataflow concerns.
READ_CALLS = {"open", "read", "read_text", "read_bytes", "load", "readlines", "readline"}
WRITE_CALLS = {"write", "writelines", "write_text", "write_bytes", "dump", "save",
               "to_csv", "to_json"}
READ_PREFIXES = ("read_", "load_")
WRITE_PREFIXES = ("write_", "to_", "save_", "dump_")
NOT_FILE_IO = {"loads", "dumps", "input", "flush", "send", "recv", "load_dotenv",
               "to_dict", "to_list", "to_numpy", "to_string", "to_frame", "to_records",
               "to_datetime", "to_numeric", "to_timedelta", "to_series", "to_bytes"}
GENERIC_IO = {"write", "read", "writelines", "readline", "readlines"}


@dataclass(frozen=True)
class Concern(ABC):
    """One concern: its name, the assertion a reviewer confirms, and its detector.

    Abstract: every concern subclasses it, sets :attr:`assertion` and implements
    :meth:`detect`.
    The instance *is* the decorator: ``@calculations`` and ``@calculations(fields=...)``
    both record the concern on the function and return it unchanged.
    """

    name: str
    #: What a marked function claims; ``--inspect`` asks whether it holds. Set per subclass.
    assertion: ClassVar[str]

    @abstractmethod
    def detect(self, v: "FunctionView") -> Optional[Evidence]:
        """``(reason, confidence)`` if ``v`` looks like it carries this concern, else None."""

    def __call__(self, fn=None, **meta):
        def mark(f):
            f.__rse_concerns__ = getattr(f, "__rse_concerns__", ()) + ((self.name, meta),)
            return f
        return mark(fn) if callable(fn) else mark


def call_name(call: ast.Call) -> Optional[str]:
    f = call.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


def dotted(node: ast.AST) -> str:
    """``a.b.c`` for a name/attribute/call expression, best effort."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return dotted(node.func)
    return ""


def _open_mode(call: ast.Call) -> str:
    args = call.args[1:2] + [k.value for k in call.keywords if k.arg == "mode"]
    return next((a.value for a in args if isinstance(a, ast.Constant)
                 and isinstance(a.value, str)), "r")


@dataclass(frozen=True)
class FunctionView:
    """Everything a detector may look at in one function body."""

    node: ast.AST        # the body only
    name: str            # lower-cased
    params: List[str]
    returns: bool        # has ``return <expr>`` or ``yield``
    reads: List[str]
    writes: List[str]
    called: Set[str]     # bare call names: ``shuffle``
    dotted: List[str]    # dotted call paths: ``client.chat.completions.create``
    
    @classmethod
    def of(cls, node: ast.AST) -> "FunctionView":
        body = ast.Module(body=node.body, type_ignores=[])   # not the decorator list
        calls = [n for n in ast.walk(body) if isinstance(n, ast.Call)]
        reads, writes = set(), set()
        for c in calls:
            name = call_name(c)
            if not name or name in NOT_FILE_IO:
                continue
            if name == "open":
                mode = _open_mode(c)
                (writes if any(ch in mode for ch in "wxa+") else reads).add(f'open("{mode}")')
            elif name in WRITE_CALLS or name.startswith(WRITE_PREFIXES):
                writes.add(name)
            elif name in READ_CALLS or name.startswith(READ_PREFIXES):
                reads.add(name)
        a = node.args
        params = [p.arg for p in a.posonlyargs + a.args + a.kwonlyargs]
        params += [p.arg for p in (a.vararg, a.kwarg) if p]
        returns = any((isinstance(n, ast.Return) and n.value is not None)
                      or isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(body))
        return cls(node=body, name=node.name.lower(), params=params, returns=returns,
                   reads=sorted(reads), writes=sorted(writes),
                   called={n for c in calls if (n := call_name(c))},
                   dotted=[d for c in calls if (d := dotted(c.func))])

    @property
    def does_io(self) -> bool:
        return bool(self.reads or self.writes)

    def hits(self, tokens=(), names=()) -> List[str]:
        """Calls whose dotted path contains one of ``tokens`` or whose name is in ``names``."""
        return sorted({d for d in self.dotted if any(t in d.lower() for t in tokens)}
                      | (self.called & set(names)))
