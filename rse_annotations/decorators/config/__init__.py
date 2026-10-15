"""@config: supplies a threshold, hyperparameter or path."""
from .._base import Concern


def detect(v):
    if v.returns and not v.params and not v.does_io:
        return "returns a value with no inputs and no I/O", "medium" if v.called else "high"
    return None


CONCERN = Concern(
    "config",
    "Does this value land in the run's provenance record?",
    detect)
