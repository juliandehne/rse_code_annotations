# rse_code_annotations — Concept

A lightweight Python framework that uses **decorators** to mark the
*role* each function plays in a data-processing pipeline, plus a small **interactive
tool** that helps the author review the purely mathematical parts and scaffold tests
for every decorated function. No LLM, no network.

The motivating problem: LLM-generated code is easy to produce but hard to audit. If the
author labels *what each function is supposed to be* (a pure function, a format mapping,
an input boundary, an output boundary), a machine can check that the label holds and
focus human review where it matters most — the maths.

---

## 1. The decorators

All are exported from `rse_annotations`. They attach reflection metadata
to the function (a `__rse_decorator__` record) without changing its runtime behaviour, so
they are safe to leave in production code.

| Decorator       | Marks code that…                                              | Runner focus |
| --------------- | ------------------------------------------------------------- | ------------ |
| `@functional`   | is a **mathematical function** — deterministic, pure, output depends only on inputs (no I/O, no globals). | Extract the source as a **reviewable snippet**; **infer and show its formula**; generate a pattern-based unit-test stub. |
| `@mapping`      | **maps/transforms** one data format or object into another.   | Must have a docstring documenting its fields; is exercised by unit tests. |
| `@data_input`   | is a **boundary where data enters** the system (reads a file / source). | Must actually **read** a file successfully; must document its fields. |
| `@data_output`  | is a **boundary where data leaves** the system (writes a file / sink). | Must actually **write** a file successfully; must document its fields. |

### Why decorators (reflection) *and* AST scanning

Decorators give us two things a static scan cannot: (a) a reliable, import-time **registry**
of every decorated function with its module/line location, and (b) the ability to **wrap**
boundary functions so the runner can observe real file I/O at test time.

But reflection is structurally blind to the question *"what is **not** decorated?"* — an
undecorated function never runs a decorator, so it never enters the registry. And research
code very often does not import at all (an optional dependency is missing, a script calls
`sys.exit()` at module scope, an API key is read at import time). Both are exactly the
conditions under which you most want an audit.

So the design is a **hybrid**:

| | Reflection (import) | AST (parse only) |
| --- | --- | --- |
| Sees | decorated functions | **every** function, decorated or not |
| Needs the code to import | yes | no |
| Used for | discovery, formula inference, stub generation, I/O-success checks | placement checks (§3), **coverage + candidates** (§5) |

---

## 2. Metadata attached by each decorator

```python
@dataclass
class DecoratorInfo:
    concern: str              # one of REVIEW_CONCERNS (derived from the DECORATORS tuple)
    func: Callable            # the wrapped function
    qualname: str             # module-qualified name
    module: str               # defining module
    file: str                 # source file
    lineno: int               # definition line
    fields: dict | None       # optional declared field schema (for docstring cross-check)
```

Every decorated function also gets `func.__rse_decorator__ = DecoratorInfo(...)` and is
appended to a process-global `REGISTRY`.

---

## 3. The checking runner

`Runner(...).run()` (the library's programmatic checker) does the following, per
decorated function:

1. **Discovery** — import the target (by dotted name, or by walking a directory with
   `discover_path`); collect everything in `REGISTRY`.
2. **Placement checks** (AST) — verify the decorator is applied where it makes sense:
   - decorator is the outermost one and applied to a `def`/`async def`, not a class;
   - `@functional` bodies contain **no** `open(`, no `print(`, no obvious I/O calls, and no
     use of module-level globals (a heuristic purity lint);
   - `@data_input` / `@data_output` bodies **do** contain a file-read / file-write call
     respectively (they are on the boundary they claim to be).
3. **Unit tests** — run any `pytest`/`unittest` tests the author wrote for these functions
   (discovered by naming convention `test_<name>` or a user-supplied test path).
4. **Non-`@functional` I/O + doc checks** — for `@mapping`, `@data_input`, `@data_output`:
   - **docstring / field docs**: the function must have a docstring, and if it declares
     `fields=...` every field must be mentioned in the docstring (pythondoc-style);
   - **I/O success** (`data_input`/`data_output` only): run the function against a sandbox
     fixture and confirm a file was actually read / written (observed via a traced `open`).
5. **`@functional` correctness aid** — instead of asserting maths (undecidable in general),
   the runner **emits a list of code snippets** — one per `@functional` — that the author
   can iterate over to review mathematical correctness by eye, and **infers each one's
   formula** for inspection (see §4 for the tool that drives this interactively).

The runner returns a structured `Report` (JSON-serialisable) and a human-readable summary
with PASS / WARN / FAIL per function.

---

## 4. The interactive tool (three options)

`python -m rse_annotations.cli <path>` is the front door. It walks `<path>` (default:
the current directory), imports every `*.py` under it so decorators register, collects
the decorated functions, and offers a **three-option menu** — no LLM, no network:

**Option 1 — Inspect `@functional` functions.** Each `@functional` snippet is shown
one at a time with its source and its **inferred formula** (§ formula inference in the
README). The author accepts or declines each (`[y]es / [n]o / [s]kip`); verdicts are
written to `<path>/inspection.yaml` and re-loaded on the next run. This is aimed at
reviewing *generated* code: seeing the rendered formula next to the source makes it
easy to judge whether the maths matches intent.

**Option 2 — Generate unit-test stubs.** For every decorated function the tool emits a `pytest`
stub built from the function's **review-concern pattern** — purely mechanical, no model:

- `@functional` → a determinism check (same inputs → same output) plus an
  expected-value scaffold, with the inferred formula included as a comment;
- `@mapping` → a shape-transform check;
- `@data_input` / `@data_output` → a `tmp_path` read / write check.

Every stub body calls `pytest.skip("TODO: ...")`, so a generated test never silently
passes until the author fills it in — it cannot bless wrong maths. Files are written to
`<path>/tests/test_<module>.py` (the conventional Python test location).

**Option 3 — Report decorator coverage.** The static audit described in §5.

`--inspect` / `--stubs` / `--coverage` jump straight to one option and skip the menu.

---

## 5. Coverage and candidates (static, no import)

Options 1 and 2 act on what *is* decorated. Option 3 answers the prior question — **how
much of this codebase is decorated at all, and what should be next?** — which is the
question you actually have when handed a pile of AI-generated research software.

`scan_path(root)` parses every `*.py` under `root` with `ast` (nothing is imported and
nothing is executed), walks the module/class/function structure, and produces one
`FunctionRecord` per function and method:

- **Coverage.** How many eligible functions carry a decorator, broken down
  per review concern and per file. *Eligible* excludes dunder methods, nested closures and test
  functions, so the denominator is not inflated by things a decorator would be
  meaningless on. Those exclusions are reported, not hidden.
- **Candidates.** For each *undecorated* function, the decorator it most likely deserves,
  inferred from the same syntax the placement checks use, with a `high`/`medium`/`low`
  confidence and a stated reason:

  | Body shape | Suggestion |
  | --- | --- |
  | writes a file (`to_csv`, `write_text`, `open(p, "w")`, …) | `@data_output` |
  | reads a file (`read_csv`, `open(p)`, …) | `@data_input` |
  | **both** reads and writes | `@data_output`, low confidence — *"consider splitting"* |
  | arithmetic only, returns a value, no I/O | `@functional` |
  | takes input, returns a transformed value, no I/O | `@mapping` |
  | returns nothing, does no I/O | *not a candidate* — procedural glue |

  `open` is classified by its **mode**, not its name, so `open(p, "w")` is a write. Names
  that only *look* like I/O (`json.loads`, `df.to_dict`, `pd.to_numeric`) are excluded, or
  the `read_`/`to_` prefix rules would label half of pandas as a boundary. A bare
  `x.write(...)` is reported but never at high confidence — it may be a logger.

The suggestions are a **worklist for a human**, not a verdict. The report is printed as a
table and written in full to `<path>/decorator_coverage.md`.

---

## 6. Package layout

```
rse_code_annotations/
├── README.md                     # quickstart
├── pyproject.toml
├── ideas/                        # design notes (this document, ARCHITECTURE.md, ...)
├── rse_annotations/
│   ├── __init__.py               # re-exports the decorators + helpers
│   ├── __main__.py / cli.py      # `python -m rse_annotations <path>` (mode menu)
│   ├── legacy.py                 # deprecated Runner/Report, kept for old callers
│   ├── decorators/               # the marks themselves
│   │   ├── markers.py            # the decorators, DECORATORS, HazardDecorator enum
│   │   ├── registry.py           # DecoratorInfo, REGISTRY
│   │   └── discovery.py          # import by dotted name or by walking a path
│   ├── core/                     # object model: TargetProject, Plugin, Audit, findings
│   ├── scan/                     # static (AST-only) scan, never imports the target
│   │   ├── scanner.py            # scan_path: files -> CoverageReport
│   │   ├── candidates.py         # decorator suggestion from the body's shape
│   │   ├── hazards.py            # HazardKind objects, HAZARD_KINDS, propagation
│   │   ├── vocabulary.py         # evidence tokens, data only
│   │   └── model.py, ast_utils.py
│   ├── inspection/               # human review of @functional code
│   │   ├── review.py             # Reviewer: the interactive accept/decline loop
│   │   ├── verdicts.py           # Verdict, VerdictStore (inspection.yaml)
│   │   ├── formula.py            # AST / SymPy / latexify formula inference
│   │   └── snippets.py           # reviewable source snippets
│   ├── testing/                  # pytest stub generation, differential verification
│   ├── reporting/                # coverage report + renderers
│   └── plugins/hazards/<name>/   # one folder per plugin; human_code_inspection is
│                                 #   the worked example (incl. its automatic checks.py)
├── examples/
│   └── sample_pipeline.py        # one function per review concern, correct + incorrect
└── tests/
```

## 7. Audit hazards (static, no import)

The dataflow decorators answer **"where does data flow?"**. The first full coverage run (on the
`lni_study` testbed) showed that this leaves the audit questions unasked: the study's LLM
call, its corpus sampler and its headline statistic all land in `@mapping`, which absorbed
54% of candidates and is therefore closer to a residual than a category.

So `scan_path` also reports a second, **orthogonal** axis — **"where can the result be
wrong, and can I reproduce it?"** Most hazards *refine* a dataflow decorator: they add a
contract of their own to the typical parent's. In code this is a reference
(`HazardKind(parent=HazardDecorator.FUNCTIONAL)`), not a subclass, and it is only shown
for orientation: a function's decorator and its hazards are found independently
(`compute_dimension_icr` is `@mapping` and `statistical`).

| Hazard | Typically refines | The claim it makes |
| --- | --- | --- |
| `@model_call` | `@data_input` | data enters from a **model** — non-deterministic, and no failure path may fabricate |
| `@human_input` | `@data_input` | data enters from a **person** (coding / annotation / gold standard) — the coders, the codebook version and an inter-coder reliability figure must be recoverable |
| `@external_tool` | — | the computation **leaves the process** — the binary and its **version** are part of the method, and a missing one must fail loudly |
| `@stochastic` | `@functional` | pure **given the seed** — so the seed must be a parameter, and same-seed calls must agree |
| `@statistical` | `@functional` | returns a number the paper reports — must be pinned against a reference implementation |
| `@unit_of_analysis` | `@mapping` | records in, **fewer** records out — every drop needs a logged reason |
| `@config` | — | supplies a threshold/hyperparameter — must land in the provenance record |
| `@human_decision` | — | a person decides here, **at run time** — the judgement, decider and time must be recorded |
| `@validation` | — | asserts a property of the data — and **a guard nobody calls is worse than no guard** |

`@model_call` and `@human_input` are deliberately siblings: in an AI-assisted study every
datum was produced by a model or by a person, and an audit that cannot say **which** is not
an audit. `@external_tool` is the one hazard with no dataflow parent — a subprocess may
read, write, both or neither, which is exactly why the dataflow decorators cannot see it.

A function has **one dataflow role and zero or more hazards**, so hazards are computed for
decorated functions too. Three details make the map usable on real code:

- **Provenance hazards propagate along the call graph.** `classify_paper` never touches the
  OpenAI client — it calls `_complete_with_retries`, which does. Callers inherit the hazard,
  marked `indirect`. The dangerous call is always a few layers down. Only the four "where did
  this value come from?" hazards travel (model, person, subprocess, RNG); `@config` and
  `@validation` are properties of the function itself.
- **Only randomness that reaches the result counts.** `random.random()` used to jitter a
  retry backoff is not a reproducibility hazard, and flagging it would (via propagation)
  taint every function above it.
- **A filename is evidence; a sentence is not.** Human provenance is keyed on path literals
  (`coding_*.csv`, `gold_human_*`), never on prose — an argparse `help=` string that mentions
  the goldstandard says nothing about what the function reads. For the same reason the token
  *annotation* is not a human marker: in the testbed `annotations_*_checkpoint.csv` is the
  **model's** output.

Each row of the table is one `HazardKind` in `scan/hazards.py`; `HAZARD_KINDS` is the
single source from which the lookup tables (`HAZARDS`, `HAZARD_PARENT`, `HAZARD_HELP`,
`CRITICAL_HAZARDS`) are derived. The tokens each detector looks for are plain data in
`scan/vocabulary.py`.

This is **detection, not enforcement** — no decorator, no runtime check yet.
[`PROPOSED_ANNOTATIONS.md`](PROPOSED_ANNOTATIONS.md) works through the evidence, the
checkable contract for each hazard, and what enforcement would take.

---

## 8. Non-goals

- Proving mathematical correctness automatically (we *assist* review, not replace it).
- Enforcing purity at runtime (the purity check is a best-effort static lint).
- Being a general test framework — it wraps `pytest`/`unittest`, it does not replace them.
- Deciding for you what to decorate — coverage produces a *worklist*, not a verdict, and
  its suggestions carry an explicit confidence for exactly that reason.
