# rse_code_annotations — Concept

A lightweight Python framework that uses **code annotations (decorators)** to mark the
*role* each function plays in a data-processing pipeline, plus a small **interactive
tool** that helps the author review the purely mathematical parts and scaffold tests
for every annotated function. No LLM, no network.

The motivating problem: LLM-generated code is easy to produce but hard to audit. If the
author labels *what each function is supposed to be* (a pure function, a format mapping,
an input boundary, an output boundary), a machine can check that the label holds and
focus human review where it matters most — the maths.

---

## 1. The four annotations

All four are decorators exported from `rse_annotations`. They attach reflection metadata
to the function (a `__rse_annotation__` record) without changing its runtime behaviour, so
they are safe to leave in production code.

| Annotation      | Marks code that…                                              | Runner focus |
| --------------- | ------------------------------------------------------------- | ------------ |
| `@functional`   | is a **mathematical function** — deterministic, pure, output depends only on inputs (no I/O, no globals). | Extract the source as a **reviewable snippet**; **infer and show its formula**; generate a pattern-based unit-test stub. |
| `@mapping`      | **maps/transforms** one data format or object into another.   | Must have a docstring documenting its fields; is exercised by unit tests. |
| `@data_input`   | is a **boundary where data enters** the system (reads a file / source). | Must actually **read** a file successfully; must document its fields. |
| `@data_output`  | is a **boundary where data leaves** the system (writes a file / sink). | Must actually **write** a file successfully; must document its fields. |

### Why decorators (reflection) and not pure AST scanning?

Decorators give us two things a static scan cannot: (a) a reliable, import-time **registry**
of every annotated function with its module/line location, and (b) the ability to **wrap**
boundary functions so the runner can observe real file I/O at test time. We still use the
`ast` module for the *placement* checks (see §3), so the design is a hybrid: reflection for
discovery + observation, AST for structural validation.

---

## 2. Metadata attached by each annotation

```python
@dataclass
class AnnotationInfo:
    kind: str                 # "functional" | "mapping" | "data_input" | "data_output"
    func: Callable            # the wrapped function
    qualname: str             # module-qualified name
    module: str               # defining module
    file: str                 # source file
    lineno: int               # definition line
    fields: dict | None       # optional declared field schema (for docstring cross-check)
```

Every decorated function also gets `func.__rse_annotation__ = AnnotationInfo(...)` and is
appended to a process-global `REGISTRY`.

---

## 3. The checking runner

`Runner(...).run()` (the library's programmatic checker) does the following, per
annotated function:

1. **Discovery** — import the target (by dotted name, or by walking a directory with
   `discover_path`); collect everything in `REGISTRY`.
2. **Placement checks** (AST) — verify the annotation is applied where it makes sense:
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

## 4. The interactive tool (two options)

`python -m rse_annotations.cli <path>` is the front door. It walks `<path>` (default:
the current directory), imports every `*.py` under it so decorators register, collects
the annotations, and offers a **two-option menu** — no LLM, no network:

**Option 1 — Inspect `@functional` annotations.** Each `@functional` snippet is shown
one at a time with its source and its **inferred formula** (§ formula inference in the
README). The author accepts or declines each (`[y]es / [n]o / [s]kip`); verdicts are
written to `<path>/inspection.yaml` and re-loaded on the next run. This is aimed at
reviewing *generated* code: seeing the rendered formula next to the source makes it
easy to judge whether the maths matches intent.

**Option 2 — Generate unit-test stubs.** For every annotation the tool emits a `pytest`
stub built from the function's **kind pattern** — purely mechanical, no model:

- `@functional` → a determinism check (same inputs → same output) plus an
  expected-value scaffold, with the inferred formula included as a comment;
- `@mapping` → a shape-transform check;
- `@data_input` / `@data_output` → a `tmp_path` read / write check.

Every stub body calls `pytest.skip("TODO: ...")`, so a generated test never silently
passes until the author fills it in — it cannot bless wrong maths. Files are written to
`<path>/test_stubs/test_<module>.py`.

`--inspect` / `--stubs` jump straight to one option and skip the menu.

---

## 5. Package layout

```
rse_code_annotations/
├── CONCEPT.md                  # this document
├── README.md                   # quickstart
├── pyproject.toml
├── rse_annotations/
│   ├── __init__.py             # re-exports the four decorators + Runner + helpers
│   ├── annotations.py          # @functional / @mapping / @data_input / @data_output
│   ├── registry.py             # AnnotationInfo, REGISTRY, KINDS/KIND_HELP
│   ├── discovery.py            # import by dotted name or by walking a path
│   ├── checks.py               # AST placement + docstring + I/O-success checks
│   ├── snippets.py             # reviewable source snippets (no deps)
│   ├── formula.py              # AST / SymPy / latexify formula inference
│   ├── stubs.py                # pattern-based pytest stub generation (no LLM)
│   ├── inspection.py           # interactive @functional review + inspection.yaml
│   ├── verify.py               # differential-testing harness
│   ├── runner.py               # orchestration + Report
│   └── cli.py                  # `python -m rse_annotations.cli <path>` (two-option menu)
├── examples/
│   └── sample_pipeline.py      # one function of each kind, correct + incorrect
└── tests/
    └── test_framework.py
```

## 6. Non-goals

- Proving mathematical correctness automatically (we *assist* review, not replace it).
- Enforcing purity at runtime (the purity check is a best-effort static lint).
- Being a general test framework — it wraps `pytest`/`unittest`, it does not replace them.
