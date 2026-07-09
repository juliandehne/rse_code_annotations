"""I/O fixtures for the sample pipeline's boundary functions.

Point the runner at this with ``--fixtures examples.fixtures:FIXTURES``. Each fixture
receives the sandbox ``tmpdir`` (and the open-tracer, unused here) and returns the
positional/keyword arguments to invoke the boundary function with. For ``data_input``
fixtures, prepare a real input file inside ``tmpdir`` first.
"""

from __future__ import annotations

import os


def _load_csv_fixture(tmpdir, tracer):
    path = os.path.join(tmpdir, "in.csv")
    # NOTE: written with the *original* open via the tracer's saved reference would
    # count as a write; use a plain file write here so only the read is observed.
    with open(path, "w", newline="") as fh:
        fh.write("name,score\na,1.0\nb,2.0\n")
    # Reset the tracer so the setup write above isn't counted against the read check.
    tracer.reads.clear()
    tracer.writes.clear()
    return (path,), {}


def _dump_json_fixture(tmpdir, tracer):
    path = os.path.join(tmpdir, "out.json")
    return (path, [{"name": "a", "score": 1.0}]), {}


#: Mapping consumed by the CLI ``--fixtures`` option.
FIXTURES = {
    "load_csv": _load_csv_fixture,
    "dump_json": _dump_json_fixture,
}
