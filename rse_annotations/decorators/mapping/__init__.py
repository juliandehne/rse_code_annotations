"""@mapping: code that transforms one data format or object into another."""
from .._base import Concern


def detect(v):
    if v.does_io or not v.returns or not v.params:
        return None
    if "print" in v.called:
        return "returns a value but also prints: report/format helper", "low"
    calls = f" (calls {', '.join(sorted(v.called)[:3])})" if v.called else ""
    return f"input in, transformed value out, no I/O{calls}", "medium"


CONCERN = Concern(
    "mapping",
    "Does this transformation keep every record and field it should, and nothing else?",
    detect)
