"""@data_output: a boundary where data leaves the system (writes a sink/file)."""
from .._base import GENERIC_IO, Concern


class DataOutput(Concern):
    def detect(self, v):
        if not v.writes:
            return None
        if v.reads:
            return (f"reads ({', '.join(v.reads[:3])}) and writes ({', '.join(v.writes[:3])}): "
                    f"consider splitting into @data_input + @data_output", "low")
        specific = [w for w in v.writes if w not in GENERIC_IO]
        hint = "" if specific else " (may be a logger/stream, not a file)"
        return f"writes {', '.join(v.writes[:3])}{hint}", "high" if specific else "medium"


CONCERN = DataOutput(
    "data_output",
    "Is everything a reader needs to regenerate this output written alongside it?")
