"""Example pipeline exercising all four annotations.

Point the interactive tool at this directory::

    python -m rse_annotations.cli examples

or check it programmatically with ``Runner("examples.sample_pipeline").run()``.

It intentionally includes one *good* and one *problematic* case so the checks show
both PASS and FAIL/WARN outcomes.
"""

from __future__ import annotations

import csv
import json
from typing import Dict, List

from rse_annotations import data_input, data_output, functional, mapping


# --- @functional: pure maths, no I/O (should PASS placement) --------------- #

@functional
def normalize(value: float, lo: float, hi: float) -> float:
    """Scale ``value`` into the unit interval given range [lo, hi].

    :param value: the raw measurement.
    :param lo: lower bound of the range.
    :param hi: upper bound of the range.
    :returns: (value - lo) / (hi - lo).
    """
    return (value - lo) / (hi - lo)


@functional
def mean(values: List[float]) -> float:
    """Arithmetic mean of a non-empty sequence.

    :param values: the numbers to average.
    :returns: sum(values) / len(values).
    """
    return sum(values) / len(values)


# --- @functional that WRONGLY does I/O (should FAIL placement) ------------- #

@functional
def impure_sum(path: str) -> float:
    """A deliberately mis-annotated function: reads a file, so not pure."""
    with open(path) as fh:
        return sum(float(line) for line in fh)


# --- @data_input: reads a file (should PASS placement + io_success) -------- #

@data_input(fields={"path": "CSV file to read", "rows": "parsed records"})
def load_csv(path: str) -> List[Dict[str, str]]:
    """Read records from a CSV file.

    :param path: the CSV file to read.
    :returns rows: a list of dict records, one per row.
    """
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


# --- @mapping: transforms one format into another (needs docstring) -------- #

@mapping(fields={"rows": "input records", "out": "records with float 'score'"})
def coerce_scores(rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """Convert the string ``score`` field of each record into a float.

    :param rows: input records with a string 'score'.
    :returns out: records whose 'score' is a float.
    """
    return [{**r, "score": float(r["score"])} for r in rows]


# --- @data_output: writes a file (should PASS placement + io_success) ------ #

@data_output(fields={"path": "destination JSON file", "records": "data to write"})
def dump_json(path: str, records: List[Dict[str, object]]) -> None:
    """Write ``records`` to a JSON file.

    :param path: destination JSON file.
    :param records: the data to write.
    """
    with open(path, "w") as fh:
        json.dump(records, fh)


# --- @mapping missing a docstring (should FAIL docstring check) ------------ #

@mapping
def untidy(rows):  # noqa: D401,ANN001,ANN201 - intentionally undocumented
    return rows
