# rse_code_annotations

Role **annotations** for (generated) Python code, plus a **runner** that checks the
annotations hold and helps you review the maths.

See [`CONCEPT.md`](CONCEPT.md) for the full design rationale.

## Install

```bash
pip install -e .            # core, no dependencies — the annotations work immediately
pip install -e ".[formula]" # + SymPy/latexify for formula inference
pip install -e ".[fable]"   # + anthropic SDK for Fable test-stub generation
```

The base install has **no dependencies**: after `pip install` you can import and
apply the four annotations right away. The optional extras only add the heavier
`run`-time analysis (formula inference, Fable).

The runner is invoked with `python -m rse_annotations.cli` — this needs nothing on
your PATH; the interpreter finds the installed package via `site-packages`. (A
`rse-annotations` console script is also installed for convenience, but using it as
a bare command requires Python's `Scripts` dir on PATH, so the docs use `python -m`.)

## The four annotations

```python
from rse_annotations import functional, mapping, data_input, data_output

@functional
def normalize(v, lo, hi):
    "Scale v into [0,1]. :param v: :param lo: :param hi: :returns:"
    return (v - lo) / (hi - lo)

@data_input(fields={"path": "CSV to read", "rows": "parsed records"})
def load_csv(path):
    "Read rows. :param path: :returns rows:"
    with open(path) as fh:
        ...
```

| Annotation     | Means                                          | Runner checks |
| -------------- | ---------------------------------------------- | ------------- |
| `@functional`  | pure mathematical function                     | purity (no I/O); emits a review snippet + optional test stub |
| `@mapping`     | transforms one format/object into another      | has docstring; documents declared fields |
| `@data_input`  | boundary where data enters (reads a file)      | actually reads a file; documents fields |
| `@data_output` | boundary where data leaves (writes a file)     | actually writes a file; documents fields |

## The runner

The runner has three subcommands. It works on **any** target: name an importable
module and (if it lives outside the cwd) point `--path` at its source root. The
target is never installed — it is just added to `sys.path` and imported for
inspection.

```bash
# 1. What can I annotate?  Lists the kinds so you can choose one to apply.
python -m rse_annotations.cli kinds

# 2. What is already annotated?  Inventories EXISTING annotations in a target.
python -m rse_annotations.cli list mypkg --path src

# 3. Do the annotations hold?  Full checks + formula inference + Fable.
python -m rse_annotations.cli run mypkg --path src --fixtures mypkg.fixtures:FIXTURES
```

`kinds` and `list` are the menu the newcomer starts with: `kinds` prints the four
roles and their one-line guidance; `list` scans a target and reports which
functions already carry an annotation, grouped by kind. `run` is the full checker.

```bash
# text report
python -m rse_annotations.cli run examples.sample_pipeline --fixtures examples.fixtures:FIXTURES

# JSON, and skip Fable entirely
python -m rse_annotations.cli run examples.sample_pipeline --no-stubs --json
```

The `run` exit code is `0` when no check fails, `1` otherwise — usable in CI.

### Fixtures (for the I/O-success check)

Boundary functions (`@data_input` / `@data_output`) are *invoked* in a sandbox to
confirm they really read/write. Supply a `dict` mapping function name → a
`fixture(tmpdir, tracer) -> (args, kwargs)` callable (see `examples/fixtures.py`).
Without a fixture the I/O check is reported as `WARN` (cannot invoke safely).

## Fable-assisted `@functional` review

For every `@functional`, the runner prints the source as a **review snippet**. If
**Claude Fable 5** is available (the `anthropic` SDK is installed, `ANTHROPIC_API_KEY`
is set, and a probe call succeeds), it also drafts a `pytest` **stub** per snippet —
scaffolding with `# TODO` asserts and property-test ideas, never fabricated expected
values. If Fable is unavailable the runner degrades to snippet-only mode and says why.

Flags: `--no-stubs` (never call Fable), `--no-probe` (assume available if a key is
set), `--effort {low,medium,high,xhigh,max}`.

The integration uses server-side refusal fallback to `claude-opus-4-8` by default and
requires 30-day data retention (it will not run under zero-data-retention).

## Formula inference for `@functional`

For every `@functional` the runner also **infers the mathematical formula from the code
and prints it for inspection** (never a correctness proof). Three backends run
best-effort: AST rendering (no deps), SymPy symbolic execution (`pip install sympy`),
and latexify (`pip install latexify-py`). Install both with `pip install -e ".[formula]"`.
See [`FORMULA_INFERENCE.md`](FORMULA_INFERENCE.md) for the landscape (why symbolic
tools recover closed forms for scalar arithmetic, why Krippendorff's α needs a reference
implementation instead, and where formal verifiers like Dafny/Why3/Coq fit). Disable
with `--no-formulas`.

## Differential verification

Formula inference *renders* the maths; it does not *prove* it. To pin correctness,
the library ships a generic differential-testing harness:

```python
from rse_annotations import differential_check

res = differential_check(candidate=my_impl, reference=trusted_impl,
                         gen_inputs=lambda rng: (rng.uniform(-9, 9),), trials=200)
print(res.summary())   # e.g. "200 checked, 0 skipped, worst |delta| 4.4e-16"
assert res.ok
```

`candidate` and `reference` are run on the same seeded random inputs; a reference
that raises (or returns a sentinel) marks a trial out-of-domain and skips it. This
is how the Krippendorff example below verifies its transparent closed form against
the external `krippendorff` library — but the harness is domain-agnostic.

## Example: Krippendorff's α

Krippendorff's α is **one worked example**, not part of the framework. It shows the
honest pipeline for a formula buried inside a third-party library call: isolate the
maths as a pure `@functional`, let `run` render its formula, and pin it with
`differential_check` against the trusted library. See the `lni_study` testbed and
[`FORMULA_INFERENCE.md`](FORMULA_INFERENCE.md) for the full write-up.

## Test

```bash
pytest        # network-free; Fable calls are disabled in tests
```
