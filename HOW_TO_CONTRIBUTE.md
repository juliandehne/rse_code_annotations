# How to contribute: add a concern

A concern is one folder under `rse_annotations/decorators/`. The folder holds both the
decorator and a static detector, and it is discovered automatically. This tutorial
builds `hardware_dependency` from scratch. That concern is already in the repo, so you
can compare your result with
[`rse_annotations/decorators/hardware_dependency/concern.py`](rse_annotations/decorators/hardware_dependency/concern.py).

**The concern.** A result that depends on the hardware it ran on (GPU vs CPU, driver,
precision) is not reproducible unless that dependency is recorded. A reviewer should
ask: *Are the device, driver and precision recorded, and does the result hold on other
hardware?*

## Step 1: Create the folder

```
rse_annotations/decorators/hardware_dependency/__init__.py   # only a one-line docstring
rse_annotations/decorators/hardware_dependency/concern.py    # the logic
```

`__init__.py` only makes the folder a package; it holds no code. Everything goes into
`concern.py`.

The folder name must be a valid Python identifier, because users will import it as
`from rse_annotations import hardware_dependency`.

## Step 2: Write the detector

A concern is a subclass of the abstract base class `Concern`. `Concern.detect` is an
abstract method (`@abstractmethod`, the Python counterpart of an `abstract` method in
Java): a subclass that does not implement it cannot be instantiated and fails with
`TypeError: Can't instantiate abstract class ...`.

`detect` gets a `FunctionView` of the function **body** and returns either `None` or
a pair `(reason, confidence)`. The confidence is one of `"high"`, `"medium"` or `"low"`.

What a `FunctionView` offers (see `decorators/_base.py`):

| Field | Example |
|---|---|
| `v.name` | `"add_on_gpu"` (lower-cased) |
| `v.params` | `["x", "k"]` |
| `v.returns` | `True` if there is a `return <expr>` or `yield` |
| `v.called` | bare call names: `{"device", "constant", "add"}` |
| `v.dotted` | dotted call paths: `["tf.device", "tf.constant", ...]` |
| `v.reads`, `v.writes`, `v.does_io` | file I/O found in the body |
| `v.hits(tokens, names)` | dotted calls containing a token, plus bare calls in `names` |
| `v.node` | the raw `ast` of the body, for anything else |

Hardware use shows up as calls like `torch.device("cuda")`, `tf.device("/GPU:0")`,
`x.cuda()` or `cupy.asarray(...)`. Write those down as tokens and use `hits`:

```python
"""@hardware_dependency: the result depends on the hardware it runs on (e.g. a GPU)."""
from .._base import Concern

TOKENS = ("cuda", "gpu", "tf.device", "torch.device", "jax.devices", "cupy",
          "set_memory_growth", "mixed_precision")


class HardwareDependency(Concern):
    def detect(self, v):
        hits = v.hits(TOKENS)
        if hits:
            return f"selects or uses an accelerator ({', '.join(hits[:2])})", "medium"
        return None
```

**Avoid short tokens.** Tokens are matched as substrings of the dotted call path. A
first version of this concern also had `"tpu"`, and it fired on every call to
`data_output` (da**ta_ou**tput → `tpu`). Run the analysis on a real project (step 5)
before you trust a vocabulary.

## Step 3: Declare the concern

At the bottom of `concern.py`, create the one instance. It is the decorator users import:

```python
CONCERN = HardwareDependency(
    "hardware_dependency",
    "Are the device, driver and precision recorded, and does the result hold on other hardware?")
```

- `name`: must equal the folder name.
- `help`: the question the reviewer answers in `--inspect`.
- `detect` (step 2): return `"high"` as confidence only for evidence
  that is hard to misread: unmarked high-confidence detections are listed in the text
  report, all others only in `--json`.

That's all. There is no list to edit: `decorators/registry.py` imports every
sub-package's `concern.py` and reads its `CONCERN`. It refuses a `name` that differs
from the folder name.

## Step 4: Use it in an example

`examples/gpu_tensors.py`:

```python
import tensorflow as tf

from rse_annotations import hardware_dependency


@hardware_dependency
def add_on_gpu():
    tf.config.set_soft_device_placement(False)   # no silent fallback to the CPU
    with tf.device("/GPU:0"):
        a = tf.constant([1.0, 2.0])
        b = tf.constant([3.0, 4.0])
        return tf.add(a, b)
```

TensorFlow does not need to be installed, because the scan never imports the file.

## Step 5: Check it on real code

```bash
python -m rse_annotations examples
```

The new row should read `hardware_dependency  1  1  0` (marked, detected, unmarked).
Then run it on a real project (see [docs/RUN_ON_TESTBED.md](docs/RUN_ON_TESTBED.md)).
Read every detection of your concern there. False positives in that list mean the
vocabulary needs fixing.

```bash
python -m rse_annotations ../lni_study/src --json | python -c "import json,sys; \
  [print(f['file'], f['qualname'], f['detected']['hardware_dependency']['reason']) \
   for f in json.load(sys.stdin)['functions'] if 'hardware_dependency' in f['detected']]"
```

## Step 6: Add a test

Add a test to `tests/test_minimal.py`, or a new `tests/test_<concern>.py`. It should
cover one case that must fire and one that must not:

```python
import textwrap

from rse_annotations.analysis import scan


def test_hardware_dependency(tmp_path):
    (tmp_path / "m.py").write_text(textwrap.dedent('''
        import torch

        def on_gpu(x):
            return x.to(torch.device("cuda"))

        def data_output_writer(rows):
            return data_output(rows)
    '''), encoding="utf-8")
    recs = {r.qualname: r for r in scan(tmp_path)[0]}
    assert "hardware_dependency" in recs["on_gpu"].detected
    assert "hardware_dependency" not in recs["data_output_writer"].detected
```

```bash
python -m pytest -q
```

## Checklist for a pull request

- [ ] `rse_annotations/decorators/<name>/concern.py`: a `Concern` subclass with `detect`, and `CONCERN`
- [ ] `name` equals the folder name; `help` is a question a reviewer can answer
- [ ] a must-fire and a must-not-fire test
- [ ] detections on a real project read through and acceptable
