# Run on the example project

`examples/` is a small, fully marked project:

- `sample_pipeline.py`: a load → transform → aggregate → write pipeline with
  `@data_input`, `@mapping`, `@calculations` and `@data_output`.
- `gpu_tensors.py`: one `@hardware_dependency` function (TensorFlow on `/GPU:0`).

One mark is deliberately wrong: `impure_sum` is marked `@calculations`, but it reads a
file.

## Analysis

```bash
python -m rse_annotations examples
```

```
8 functions, 8 marked (100%)

concern                 marked  detected  unmarked
config                       0         1         1
data_input                   1         2         1
data_output                  1         1         0
...
hardware_dependency          1         1         0
...

Detected with high confidence but not marked (all detections: --json):
  sample_pipeline.py:46  impure_sum  @data_input: reads open("r") [high]
  sample_pipeline.py:93  untidy  @calculations: pure: arithmetic only, no I/O, returns a value [high]

Marked but not detected (check the mark or the code):
  sample_pipeline.py:46  impure_sum  @calculations
```

The scan confirms every other mark. It flags `impure_sum` because a function that does
I/O is not a pure `@calculations` function. `unmarked` counts functions that look like they carry a
concern that is not marked. The text report lists only the high-confidence ones; all of
them are in `--json`:

```bash
python -m rse_annotations examples --json
```

## Inspection

```bash
python -m rse_annotations examples --inspect
python -m rse_annotations examples --inspect --concern calculations
```

Each marked function is shown with its source and the reviewer question. For example,
for `@calculations`:

```
Is this a pure function whose formula matches the method described in the paper?
[y]es / [n]o / [s]kip (default pending):
```

The verdicts go to `examples/inspection.yaml`. Delete that file to start over. It is a
generated file, so don't commit it.

## Use as a test fixture

`tests/test_minimal.py` writes a similar mini-project into a temporary directory and
checks the same things: detection, the runner output and the review loop.

```bash
python -m pytest -q
```
