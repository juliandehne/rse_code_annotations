# rse_annotations (gen_code_prototype)

Mark the research-relevant concerns of a function with a decorator, then let a static
scan tell you which functions carry concerns you have not marked, and review the marked
ones by hand.

This is the minimal prototype. The full version, with test generation, plugins and
external review, is on `main`.

## Install

```bash
pip install -e .[dev]
```

## Mark functions

```python
from rse_annotations import functional, model_call, stochastic

@functional
def scale(x, k):
    return x * k

@model_call(model="gpt-4o")
def classify(client, text):
    ...
```

A decorator only records the concern on the function (`fn.__rse_concerns__`) and returns
the function unchanged. It works both bare (`@x`) and with metadata (`@x(...)`).

## Run

```bash
python -m rse_annotations PATH              # coverage report (analysis)
python -m rse_annotations PATH --json       # the same as JSON
python -m rse_annotations PATH --inspect    # review marked functions: y / n / s(kip)
python -m rse_annotations PATH --inspect --concern functional
```

The scan only parses the code with `ast`. It never imports or runs it.

- **Analysis** lists, per function, the concerns that are marked and the ones that are
  detected. It flags *critical concerns detected but not marked* and *marked but not
  detected*. Contagious concerns (e.g. `model_call`, `stochastic`) pass to the callers.
- **Inspection** shows each marked (function, concern) pair: the source, a formula for
  single-expression `@functional` functions, and the reviewer question. Verdicts go to
  `inspection.yaml` in the scanned directory and are pre-filled on the next run.

## Layout

```
rse_annotations/
  decorators/_base.py      Concern (the decorator) + FunctionView (what detectors see)
  decorators/<concern>/    one folder per concern: vocabulary, detect(), CONCERN
  analysis/                scan + text/JSON report
  inspection/              interactive review + inspection.yaml
  __main__.py              the runner
```

## Add a concern

Create `rse_annotations/decorators/<name>/__init__.py`:

```python
from .._base import Concern

def detect(v):                     # v is a FunctionView of the function body
    hits = v.hits(tokens=("mlflow",))
    return (f"logs to {hits[0]}", "medium") if hits else None

CONCERN = Concern("experiment_tracking",
                  "Is every logged run traceable to code and data versions?",
                  detect, critical=False, contagious=False)
```

It is discovered automatically and becomes importable as
`from rse_annotations import experiment_tracking`.

## Test

```bash
python -m pytest -q
```
