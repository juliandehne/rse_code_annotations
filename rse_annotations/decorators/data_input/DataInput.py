"""@data_input: a boundary where data enters the system (reads a source/file)."""
from .._base import GENERIC_IO, Concern


class DataInput(Concern):
    assertion = "The source is documented (path, version, provenance) and its format is validated on entry."

    def detect(self, v):
        if not v.reads or v.writes:   # read-and-write is reported as data_output
            return None
        specific = [r for r in v.reads if r not in GENERIC_IO]
        hint = "" if specific else " (may be a stream, not a file)"
        return f"reads {', '.join(v.reads[:3])}{hint}", "high" if specific else "medium"
