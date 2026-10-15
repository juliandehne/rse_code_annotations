"""@calculations: a pure mathematical function (deterministic, no I/O, no globals)."""
from .._base import Concern

# Calls that keep a function pure.
MATH_SAFE = {
    "abs", "min", "max", "sum", "len", "round", "pow", "divmod",
    "float", "int", "bool", "range", "enumerate", "zip", "sorted", "isnan",
    "sqrt", "log", "log2", "log10", "exp", "sin", "cos", "tan", "floor", "ceil",
    "mean", "median", "std", "var", "array", "asarray", "zeros", "ones", "dot",
    "isclose", "sign", "prod", "clip", "nan_to_num", "count_nonzero", "unique",
}


def detect(v):
    if v.does_io or not v.returns or not v.params or v.called - MATH_SAFE:
        return None
    if not v.called:
        return "pure: arithmetic only, no I/O, returns a value", "high"
    return f"pure: arithmetic + {', '.join(sorted(v.called)[:3])}, no I/O", "medium"


CONCERN = Concern(
    "calculations",
    "Is this a pure function whose formula matches the method described in the paper?",
    detect)
