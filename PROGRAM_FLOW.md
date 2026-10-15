# Program flow

What runs, in which file, for each way of using `rse_annotations`. Support functions
are left out; the steps are the ones you would set a breakpoint on.

**Rule: nothing is computed on import.** Importing a module only runs its `import`
statements and defines constants, classes and functions. All work (finding the concerns,
scanning, reviewing) starts from an explicit call. The concern table in particular is
created by calling `decorators.load()` and then passed as an argument; there is no
global `CONCERNS`. `tests/test_minimal.py::test_import_loads_no_concern` checks this.

## Entry point

`python -m rse_annotations PATH [--analyze | --inspect] [--json] [--concern NAME]`

| Step | File | Purpose |
|---|---|---|
| 1 | `rse_annotations/__main__.py` `main()` | entry point of every option below |
| 2 | `decorators/registry.py` `load()` | build the concern table once: `{name: Concern}` |
| 3 | `__main__.py` | build the argument parser; `--concern` choices are the table's keys |
| 4 | `__main__.py` | dispatch to the analysis or the inspection, passing the table along |

`load()` does the following:

1. `names()` lists the sub-package folders of `decorators/` (`stochastic`, `calculations`, ...).
2. For each folder, `load_one(name)`:
   - derives the class name from the folder (`class_name`: `hardware_dependency` → `HardwareDependency`);
   - imports `decorators/<name>/<ClassName>.py` (this defines that concern's vocabulary constants and its class);
   - checks that the file defines a `Concern` subclass with that name;
   - creates the one instance `<ClassName>("<name>")`; a missing `detect` fails here with `TypeError` (abstract method);
   - checks that the instance has an `assertion`.

## Default / `--analyze`: coverage report

`main()` → `scan(path, concerns)` → `to_text(records, errors, concerns)` → `print`

| Step | File | Purpose |
|---|---|---|
| 1 | `analysis/scan.py` `scan()` | walk all `*.py` files under `PATH` (skips `SKIP_DIRS`, `test_*`, `conftest.py`, `setup.py`) |
| 2 | `scan.py` | read and `ast.parse` each file; the code is **never imported or run**. Parse failures go into the error list |
| 3 | `scan.py` `_functions()` | yield every top-level function and method with its qualified name |
| 4 | `decorators/_base.py` `FunctionView.of(node)` | one pass over the function **body**: parameters, returns, called names, dotted call paths, file reads/writes |
| 5 | `decorators/<name>/<ClassName>.py` `detect(view)` | called for **every** concern; returns `(reason, confidence)` or `None` → `Record.detected` |
| 6 | `scan.py` `_marked()` | decorator names on the function that are keys of the concern table → `Record.marked` |
| 7 | `scan.py` `_flag_uncalled_validations()` | a `validation` detection on a function never called anywhere in the tree is raised to high confidence |
| 8 | `analysis/report.py` `to_text()` | per concern: marked / detected / unmarked counts; then the high-confidence unmarked detections, the marked-but-not-detected functions and the parse errors |

## `--json`

Steps 1–7 as above, then `analysis/report.py` `to_json(records, errors)` dumps every
`Record` (marked, detected with reason and confidence, location) as JSON. `--json` is
ignored together with `--inspect`.

## `--inspect` (optionally `--concern NAME`): interactive review

`main()` → `review(path, concerns, concern)`

| Step | File | Purpose |
|---|---|---|
| 1 | `inspection/review.py` `review()` | locate `inspection.yaml` next to the scanned code |
| 2 | `inspection/verdicts.py` `load()` | read earlier verdicts (missing file → none); they become the defaults |
| 3 | `analysis/scan.py` `scan()` | same scan as above; only `Record.marked` is used |
| 4 | `review.py` | build the to-do list: one entry per (function, marked concern), filtered by `--concern` |
| 5 | `review.py` `formula()` | for `calculations` only: `f(...) = <expr>` if the body is a single `return` |
| 6 | `review.py` | print the source and ask `Does the assertion "<concern.assertion>" hold?` |
| 7 | `review.py` `_ask()` | read `[y]es / [n]o / [s]kip`; empty input keeps the earlier verdict |
| 8 | `inspection/verdicts.py` `dump()` | rewrite `inspection.yaml` after **every** answer (an interrupted review loses nothing); verdicts of functions not reviewed this time are kept |
| 9 | `review.py` | print the counts (accepted / declined / pending) |

## Using the decorators in research code

```python
from rse_annotations import stochastic

@stochastic
def sample(papers, seed): ...
```

| Step | File | Purpose |
|---|---|---|
| 1 | `rse_annotations/__init__.py` `__getattr__("stochastic")` | PEP 562 hook: called because `stochastic` is not a module attribute |
| 2 | `decorators/registry.py` `load_one("stochastic")` | import `stochastic/Stochastic.py` and create `Stochastic("stochastic")`; only this one concern is loaded |
| 3 | `decorators/_base.py` `Concern.__call__` | `@stochastic` / `@stochastic(...)` appends `("stochastic", meta)` to `fn.__rse_concerns__` and returns the function unchanged |

An unknown name raises `AttributeError` as usual. The scan does not need this path: it
reads decorator names from the AST.

## What runs on import

Only imports and definitions. Nothing reads files, walks directories or creates a concern.

| Module | Defined on import |
|---|---|
| `rse_annotations/__init__.py` | re-exports `Concern`, `FunctionView`, `load`, `load_one`, `names`; defines `__getattr__` |
| `__main__.py` | defines `main()`; it runs only under `python -m` (the `if __name__ == "__main__"` guard) |
| `decorators/__init__.py` | re-exports from `_base` and `registry` |
| `decorators/_base.py` | `Evidence` type alias; I/O vocabularies (`READ_CALLS`, `WRITE_CALLS`, prefixes, `NOT_FILE_IO`, `GENERIC_IO`); classes `Concern`, `FunctionView`; helpers |
| `decorators/registry.py` | functions `class_name`, `names`, `load_one`, `load` |
| `decorators/<name>/__init__.py` | a docstring only |
| `decorators/<name>/<ClassName>.py` | vocabulary constants (`TOKENS`, `RNG_CALLS`, `SEED_PARAMS`, ...) and the `Concern` subclass; imported only by `load_one` |
| `analysis/__init__.py` | re-exports `scan`, `Record`, `Finding`, `to_text`, `to_json` |
| `analysis/scan.py` | `SKIP_DIRS`; dataclasses `Finding`, `Record`; functions |
| `analysis/report.py` | functions |
| `inspection/__init__.py` | re-exports `review`, `formula`, `Verdict` |
| `inspection/review.py` | `ANSWERS` (y/n/s → verdict); functions |
| `inspection/verdicts.py` | `VERDICTS`, `VERDICT_FILE`; dataclass `Verdict`; `dump`, `load` |
