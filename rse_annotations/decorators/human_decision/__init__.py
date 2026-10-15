"""@human_decision: a person, not the machine, decides here at run time."""
from .._base import Concern

CALLS = {"input", "confirm", "prompt", "getpass"}


def detect(v):
    hits = sorted(v.called & CALLS)
    if hits:
        return f"asks a person ({', '.join(hits[:2])})", "high" if "input" in hits else "medium"
    return None


CONCERN = Concern(
    "human_decision",
    "Are the judgement, the decider and the time recorded?",
    detect)
