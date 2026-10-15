# Run on any Python project

You can point the runner at any directory or single `.py` file. The target is only
parsed, never imported, so it does not need its dependencies installed. It can be a
fresh clone of somebody else's repository.

```bash
git clone https://github.com/<someone>/<project>.git /tmp/target
python -m rse_annotations /tmp/target            # or /tmp/target/src, or one file
```

## 1. Analysis (default)

```bash
python -m rse_annotations /tmp/target
```

The report has three parts:

1. **Coverage table**: for each concern, how many functions are marked, how many look
   like they carry it (detected), and how many of those are unmarked. Concerns with
   `*` are critical.
2. **Critical concerns detected but not marked**: one line per function, with the
   evidence and a confidence. `inherits from X` means the function calls `X`, which
   carries a contagious concern such as `model_call` or `stochastic`.
3. **Marked but not detected**: marks the scan cannot confirm. Either the mark is wrong
   or the code has changed.

An undecorated project has 0 marked functions, so the report is a list of candidates
for marking. Start with the critical ones.

Scope rules: nested functions, `__dunder__` methods and `test_*` functions are skipped.
Files that do not parse are listed as errors at the end.

## 2. Machine-readable output

```bash
python -m rse_annotations /tmp/target --json > coverage.json
```

The output has one entry per function: `qualname`, `file` (relative to the target),
`lineno`, `marked` and `detected` (concern → reason, confidence, indirect).

## 3. Mark and re-run

Install the package where the target's code runs (`pip install -e <this repo>`) and add
decorators:

```python
from rse_annotations import model_call, stochastic

@model_call(model="gpt-4o")
def annotate(client, text): ...
```

Run the analysis again. The functions move from "detected but not marked" to the marked
column.

## 4. Inspection

```bash
python -m rse_annotations /tmp/target --inspect
python -m rse_annotations /tmp/target --inspect --concern functional
```

For every marked (function, concern) pair the runner shows the source, a formula (for
`@functional` functions that are a single `return`) and the reviewer question. Answer
`y` (accepted), `n` (declined) or `s` (skip, stays pending). After each answer the
verdicts are saved to `inspection.yaml` in the target directory. A later run pre-fills
them, so pressing Enter keeps the previous answer.
