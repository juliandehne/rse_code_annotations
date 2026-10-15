"""@config: supplies a threshold, hyperparameter or path."""
from .._base import Concern


class Config(Concern):
    assertion = "This value lands in the run's provenance record."

    def detect(self, v):
        if v.returns and not v.params and not v.does_io:
            return "returns a value with no inputs and no I/O", "medium" if v.called else "high"
        return None


CONCERN = Config("config")
