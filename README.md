# rse_code_annotations

Role **annotations** for (generated) Python code, plus a small interactive **tool**
that helps you review the annotated code and scaffold tests for it. No LLM, no
network.

See [`CONCEPT.md`](CONCEPT.md) for the full design rationale.

## Install

```bash
pip install -e .            # core, no dependencies — the annotations work immediately
pip install -e ".[formula]" # + SymPy/latexify for richer formula inference
```

The base install has **no dependencies**: after `pip install` you can import and
apply the four annotations right away. The optional `formula` extra only adds the
heavier symbolic backends for formula inference (the built-in AST backend needs
nothing).

The tool is invoked with `python -m rse_annotations.cli` — this needs nothing on
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

| Annotation     | Means                                          | Tool support |
| -------------- | ---------------------------------------------- | ------------ |
| `@functional`  | pure mathematical function                     | inferred formula shown for inspection; determinism + expected-value test stubs |
| `@mapping`     | transforms one format/object into another      | shape-transform test stub |
| `@data_input`  | boundary where data enters (reads a file)      | tmp-file read test stub |
| `@data_output` | boundary where data leaves (writes a file)     | tmp-file write test stub |

## The tool

The tool is an **interactive, three-option menu**. Point it at a directory (defaults
to the current directory); it walks every `*.py` file underneath, imports each so
its decorators register, and collects the annotations found there. No LLM, no
network — the three options are:

```bash
python -m rse_annotations.cli path/to/src
```

```
Found 6 annotation(s) under <root>
  functional: 3   mapping: 1   data_input: 1   data_output: 1

  1) Inspect @functional annotations
  2) Generate unit-test stubs
  3) Report annotation coverage + candidates
  q) Quit
Choose [1/2/3/q]:
```

**Option 1 — Inspect `@functional` annotations.** Each `@functional` snippet is
shown one at a time with its source and the **inferred formula**, then you accept
or decline it (`[y]es / [n]o / [s]kip`). This is meant for reviewing *generated*
code: the formula makes it easy to see whether the maths matches intent. Your
verdicts are written to `<root>/inspection.yaml` (and re-loaded on the next run so
prior decisions are shown).

**Option 2 — Generate unit-test stubs.** For every annotation, a `pytest` stub is
generated from the per-kind pattern — `@functional` gets a determinism check plus an
expected-value scaffold (with the inferred formula as a comment); `@mapping` a
shape-transform check; `@data_input`/`@data_output` a `tmp_path` read/write check.
Every stub body calls `pytest.skip(...)`, so nothing silently passes until you fill
it in. Files are written to `<root>/tests/test_<module>.py` (Python convention).

**Option 3 — Report annotation coverage.** Options 1 and 2 act on what *is* annotated.
Option 3 answers the prior question: **how much of this codebase is annotated at all,
and what should be annotated next?** It is **purely static** — every `*.py` under the
root is parsed with `ast`, nothing is imported and nothing is executed — because (a) an
unannotated function never runs a decorator, so reflection can never see it, and (b)
research code frequently will not import at all (missing optional dependency, a
`sys.exit()` at module scope, an API key read at import time).

```
Annotation coverage for <root>
  29 file(s), 267 function(s)/method(s) found; 254 eligible
  annotated: 6/254  (2%)

kind          annotated  candidates
------------  ---------  ----------
@functional   1          11
@mapping      3          113
@data_input   1          40
@data_output  1          42

Candidates for annotation (210)
suggest       conf  function                  location                      why
------------  ----  ------------------------  ----------------------------  ----------------------------------
@functional   high  compute_effective_target  src/topup_goldstandard.py:84  pure: arithmetic only, no I/O
@data_output  high  save_decisions            src/build_goldstandard.py:474 writes a file/sink: to_csv
@data_output  low   record_new_category       src/build_goldstandard.py:156 reads open("r") *and* writes open("w")
                                                                            -- consider splitting
```

Each unannotated function gets the kind its **body shape** implies (a file write →
`@data_output`; a file read → `@data_input`; pure arithmetic → `@functional`; an
argument-in/value-out transform → `@mapping`), plus a confidence and a stated reason.
Functions that are neither (`main()`, CLI glue) are listed as explicit *non-candidates*
so the denominator stays honest, as are the exclusions from it (dunders, nested helpers,
tests). `open` is judged by its **mode**, not its name. The full report — every candidate,
untruncated — is written to `<root>/annotation_coverage.md`.

The suggestions are heuristic: a **worklist for review, not a verdict**.

You can skip the menu with `--inspect`, `--stubs` or `--coverage`:

```bash
python -m rse_annotations.cli src --inspect    # straight to Option 1
python -m rse_annotations.cli src --stubs      # straight to Option 2
python -m rse_annotations.cli src --coverage   # straight to Option 3 (never imports)
```

Coverage is also available programmatically:

```python
from rse_annotations import scan_path, render_coverage_markdown

report = scan_path("path/to/src")
print(f"{report.coverage:.0%} annotated; {len(report.candidates)} candidates")
for c in report.candidates:
    print(f"  @{c.suggested} ({c.confidence}) {c.qualname} at {c.location} -- {c.reason}")
```

## Formula inference for `@functional`

Option 1 **infers the mathematical formula from the code and shows it for
inspection** (never a correctness proof). Three backends run best-effort: AST
rendering (no deps), SymPy symbolic execution (`pip install sympy`), and latexify
(`pip install latexify-py`). Install both with `pip install -e ".[formula]"`. See
[`FORMULA_INFERENCE.md`](FORMULA_INFERENCE.md) for the landscape (why symbolic tools
recover closed forms for scalar arithmetic, why Krippendorff's α needs a reference
implementation instead, and where formal verifiers like Dafny/Why3/Coq fit).

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
maths as a pure `@functional`, let the tool render its formula, and pin it with
`differential_check` against the trusted library. See the `lni_study` testbed and
[`FORMULA_INFERENCE.md`](FORMULA_INFERENCE.md) for the full write-up.

## Test

```bash
pytest        # network-free; no LLM
```
