# rse_code_annotations

Role **decorators** for (generated) Python code, plus a small interactive **tool**
that helps you review the decorated code and scaffold tests for it. No LLM, no
network.

See [`CONCEPT.md`](ideas/CONCEPT.md) for the full design rationale.

## Why

Research code is increasingly written by a machine. The scientist who publishes on
top of it is still the one answerable for whether the result is valid. That gap —
between who wrote the code and who vouches for it — is what this repository is
about.

The two obvious answers both fail in practice:

- **Read all of it.** Nobody reviews four thousand lines of plausible-looking
  generated Python line by line. Not the author, and certainly not a peer reviewer.
- **Prove all of it.** Formal verification is real, and its cost is far outside what
  a working research group can pay. (See
  [`FORMULA_INFERENCE.md`](ideas/FORMULA_INFERENCE.md) for where Dafny/Why3/Coq do fit.)

What makes inspection tractable is that **not all research code carries the
scientific claim**. Most of it is glue: argument parsing, plotting, moving files
around. Validity rests on a much smaller subset — the mathematics, and the points
where data enters and leaves the program. If a generated statistic divides by the
wrong denominator, the paper is wrong. If the `--help` text is clumsy, it is not.

So mark that subset, and spend the entire inspection budget on it:

1. **Annotate** what carries the claim — a few decorators, nothing else to learn.
2. **Inspect** it — the tool renders the *formula* the code implies, so you check a
   line of maths against your intent instead of re-reading an implementation.
3. **Test** it — a `pytest` stub per review concern, each one calling `skip()` until
   you fill it in, so nothing passes silently.
4. **Record** it — verdicts are written to `inspection.yaml`. "A human checked this"
   becomes a fact in the repository rather than a recollection.
5. **See what you have *not* looked at** — the coverage report contrasts what is
   decorated with what, by the shape of its body, should be. An inspection whose
   blind spots are invisible is indistinguishable from no inspection at all.

The deliberate limits matter as much as the features. There is no LLM and no network
anywhere in the tool: you do not audit generated code with another generator. The
formula is *rendered for a human to judge*, never proved. The coverage suggestions
are a worklist, not a verdict.

The goal is not to make review automatic. It is to make review **finite** — small
enough that a working researcher will actually do it, and legible enough that
someone else can see that it was done.

## Install

```bash
pip install -e .            # core, no dependencies — the decorators work immediately
pip install -e ".[formula]" # + SymPy/latexify for richer formula inference
pip install -r requirements.txt  # everything: package, formula extras, pytest
```

The base install has **no dependencies**: after `pip install` you can import and
apply the decorators right away. The optional `formula` extra only adds the
heavier symbolic backends for formula inference (the built-in AST backend needs
nothing).

The tool is invoked with `python -m rse_annotations` — this needs nothing on
your PATH; the interpreter finds the installed package via `site-packages`. (A
`rse-annotations` console script is also installed for convenience, but using it as
a bare command requires Python's `Scripts` dir on PATH, so the docs use `python -m`.)

## The decorators

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

| Decorator     | Means                                          | Tool support |
| -------------- | ---------------------------------------------- | ------------ |
| `@functional`  | pure mathematical function                     | inferred formula shown for inspection; determinism + expected-value test stubs |
| `@mapping`     | transforms one format/object into another      | shape-transform test stub |
| `@data_input`  | boundary where data enters (reads a file)      | tmp-file read test stub |
| `@data_output` | boundary where data leaves (writes a file)     | tmp-file write test stub |

In code, the decorator names are also the members of the `HazardDecorator` enum
(`HazardDecorator.FUNCTIONAL == "functional"`). A new decorator is one function in
`rse_annotations/decorators/markers.py`, marked `@_concern`; the enum member, the help text
and the exports are derived from it.

## The tool

Everything that *checks* something is a **plugin** under
`rse_annotations/plugins/hazards/<name>/`. A plugin offers up to three **modes**:
*human inspection*, *hazard analysis* and *test generation*. The worked example is
`human_code_inspection` (all three modes); the Responsible-RSE hazards (`licence`,
`dual_use`, `footprint`, …) are stubs that offer hazard analysis only.

There are two entry points. The **general** one asks for a mode and delegates to
every plugin that offers it (if several plugins offer inspection or test generation,
it asks which). Point it at a directory (default: the current one) or a git URL. No
LLM, no network:

```bash
python -m rse_annotations path/to/src
```

```
Scanned <root>
Found 7 decorated function(s): 3 @functional, 2 @mapping, 1 @data_input, 1 @data_output

Choose a mode:
  1) Human inspection  -- a person reviews flagged code; verdicts are recorded
  2) Hazard analysis   -- every plugin examines the code and reports findings
  3) Test generation   -- write test scaffolds
```

The **per-plugin** entry point offers only that plugin's modes plus its extra
actions — for `human_code_inspection` that is the decorator-coverage report:

```bash
python -m rse_annotations.plugins.hazards.human_code_inspection path/to/src
```

```
human_code_inspection: choose an action:
  1) Human inspection
  2) Hazard analysis
  3) Test generation
  4) Decorator coverage + candidates  (-> decorator_coverage.md)
```

What the three modes and the coverage action do for `human_code_inspection`:

**Human inspection — review `@functional` decorators.** Each `@functional` snippet is
shown one at a time with its source and the **inferred formula**, then you accept
or decline it (`[y]es / [n]o / [s]kip`). This is meant for reviewing *generated*
code: the formula makes it easy to see whether the maths matches intent. Your
verdicts are written to `<root>/inspection.yaml` (and re-loaded on the next run so
prior decisions are shown).

**Test generation — unit-test stubs.** For every decorator, a `pytest` stub is
generated from the per-kind pattern — `@functional` gets a determinism check plus an
expected-value scaffold (with the inferred formula as a comment); `@mapping` a
shape-transform check; `@data_input`/`@data_output` a `tmp_path` read/write check.
Every stub body calls `pytest.skip(...)`, so nothing silently passes until you fill
it in. Files are written to `<root>/tests/test_<module>.py` (Python convention).

**Hazard analysis.** Reports findings per facet: decorator coverage, reproducibility
hazards, `@functional`s without an accepted verdict (static), and conventions, the
inferred formulas and real I/O of the boundaries (these import the code).

**Decorator coverage.** Inspection and test generation act on what *is* decorated.
Coverage answers the prior question: **how much of this codebase is decorated at all,
and what should be decorated next?** It is **purely static** — every `*.py` under the
root is parsed with `ast`, nothing is imported and nothing is executed — because (a) an
undecorated function never runs a decorator, so reflection can never see it, and (b)
research code frequently will not import at all (missing optional dependency, a
`sys.exit()` at module scope, an API key read at import time).

```
Decorator coverage for <root>
  29 file(s), 267 function(s)/method(s) found; 254 eligible
  decorated: 6/254  (2%)

concern       decorated  candidates
------------  ---------  ----------
@functional   1          11
@mapping      3          113
@data_input   1          40
@data_output  1          42

Candidates for a decorator (210)
suggest       conf  function                  location                      why
------------  ----  ------------------------  ----------------------------  ----------------------------------
@functional   high  compute_effective_target  src/topup_goldstandard.py:84  pure: arithmetic only, no I/O
@data_output  high  save_decisions            src/build_goldstandard.py:474 writes a file/sink: to_csv
@data_output  low   record_new_category       src/build_goldstandard.py:156 reads open("r") *and* writes open("w")
                                                                            -- consider splitting
```

The scan also reports **hazards** per function (`model_call`, `stochastic`,
`statistical`, …). A function has one decorator and any number of hazards; the two are
independent. Each hazard is a `HazardKind` in `rse_annotations/scan/hazards.py` (name,
help text, flags, detector), and the names that count as evidence (`openai`, `shuffle`,
`cohen_kappa_score`, …) live in `rse_annotations/scan/vocabulary.py`. To teach the scan a
new library, extend a list there; to add a hazard, write one detector and add one entry
to `HAZARD_KINDS`.

Each undecorated function gets the kind its **body shape** implies (a file write →
`@data_output`; a file read → `@data_input`; pure arithmetic → `@functional`; an
argument-in/value-out transform → `@mapping`), plus a confidence and a stated reason.
Functions that are neither (`main()`, CLI glue) are listed as explicit *non-candidates*
so the denominator stays honest, as are the exclusions from it (dunders, nested helpers,
tests). `open` is judged by its **mode**, not its name. The full report — every candidate,
untruncated — is written to `<root>/decorator_coverage.md`.

The suggestions are heuristic: a **worklist for review, not a verdict**.

You can skip the menu (both entry points):

```bash
python -m rse_annotations src --inspect        # human inspection
python -m rse_annotations src --analyze        # hazard analysis, all plugins
python -m rse_annotations src --analyze --only human_code_inspection --format json
python -m rse_annotations src --tests          # test generation (alias: --stubs)
python -m rse_annotations src --coverage       # coverage report (never imports)
python -m rse_annotations --list               # plugins and the modes they offer
```

`--analyze` exits non-zero when a plugin reports a `fail`, so it can gate CI. New
plugins subclass `rse_annotations.Plugin` and are committed to this project: one folder
under `rse_annotations/plugins/hazards/<name>/`, added to `plugins/hazards/__init__.py`.
`human_code_inspection` is the worked example; `_stub.py` explains how to turn a stub
into a working plugin.

Coverage is also available programmatically:

```python
from rse_annotations import scan_path, render_coverage_markdown

report = scan_path("path/to/src")
print(f"{report.coverage:.0%} decorated; {len(report.candidates)} candidates")
for c in report.candidates:
    print(f"  @{c.suggested} ({c.confidence}) {c.qualname} at {c.location} -- {c.reason}")
```

## Formula inference for `@functional`

Human inspection **infers the mathematical formula from the code and shows it for
inspection** (never a correctness proof). Three backends run best-effort: AST
rendering (no deps), SymPy symbolic execution (`pip install sympy`), and latexify
(`pip install latexify-py`). Install both with `pip install -e ".[formula]"`. See
[`FORMULA_INFERENCE.md`](ideas/FORMULA_INFERENCE.md) for the landscape (why symbolic tools
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
[`FORMULA_INFERENCE.md`](ideas/FORMULA_INFERENCE.md) for the full write-up.

## Test

```bash
pytest        # network-free; no LLM
```
