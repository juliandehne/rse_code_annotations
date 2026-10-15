# rse_annotations

Research code mixes plain plumbing with steps that decide whether a result can be
trusted: model calls, random draws, human-coded data, hardware-dependent numerics. In
`rse_annotations` you mark those steps with decorators. A static scan then tells you
which functions carry a concern you have not marked, and an interactive review lets
someone check the marked ones.

```python
from rse_annotations import calculations, model_call

@calculations
def scale(x, k):
    return x * k

@model_call(model="gpt-4o")
def classify(client, text):
    ...
```

A decorator only records the concern on the function and returns it unchanged. It works
bare (`@x`) and with metadata (`@x(...)`). The scan parses the code with `ast` and never
imports or runs it.

## Install

```bash
pip install -e .[dev]
python -m pytest -q
```

## Run it

| Target | Guide |
|---|---|
| Any Python project | [docs/RUN_ON_ANY_PROJECT.md](docs/RUN_ON_ANY_PROJECT.md) |
| The testbed (lni_study, decorated branch) | [docs/RUN_ON_TESTBED.md](docs/RUN_ON_TESTBED.md) |
| The bundled example project | [docs/RUN_ON_EXAMPLES.md](docs/RUN_ON_EXAMPLES.md) |

In short: `python -m rse_annotations PATH` writes the coverage report,
`--json` writes it as JSON and `--inspect` starts the review.

## Layout

```
rse_annotations/
  decorators/_base.py      Concern (abstract base class, the decorator itself) + FunctionView
  decorators/registry.py   finds the concern folders
  decorators/<concern>/    one folder per concern; <ClassName>.py: vocabulary, Concern subclass
                           (assertion + detect()), CONCERN
  analysis/                scan + text/JSON report
  inspection/              interactive y/n/s review, writes inspection.yaml
  __main__.py              the runner
examples/                  small example project
testbed/                   runs everything against lni_study
tests/
```

## Contributing

To add a concern, create a new folder under `rse_annotations/decorators/`. The
step-by-step tutorial is [HOW_TO_CONTRIBUTE.md](HOW_TO_CONTRIBUTE.md).
