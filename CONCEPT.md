# rse_code_annotations — Concept

A lightweight Python framework that uses **code annotations (decorators)** to mark the
*role* each function plays in a data-processing pipeline, and a **runner** that verifies
those roles are used correctly, tests them, and — for the purely mathematical parts —
helps the author reason about correctness (optionally generating unit-test stubs with
Anthropic's **Claude Fable 5** model).

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
| `@functional`   | is a **mathematical function** — deterministic, pure, output depends only on inputs (no I/O, no globals). | Extract the source as a **reviewable snippet**; optionally generate unit-test stubs for correctness review. |
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

## 3. The runner

`python -m rse_annotations.cli run <package>` (or `Runner(...).run()`) does the following,
per annotated function:

1. **Discovery** — import the target package/module; collect everything in `REGISTRY`.
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
   can iterate over to review mathematical correctness by eye, and offers to **generate
   unit-test stubs** for each snippet *if Fable is available* (see §4).

The runner returns a structured `Report` (JSON-serialisable) and a human-readable summary
with PASS / WARN / FAIL per function.

---

## 4. Fable-assisted unit-test stubs (optional)

For `@functional` snippets the runner can call **Claude Fable 5** (`claude-fable-5`) via the
official `anthropic` Python SDK to draft `pytest` stubs the author then reviews and fills in.

"**if fable is still available**" is checked at runtime, in this order — the feature is fully
optional and the runner degrades gracefully to *snippet-only* mode if any check fails:

1. the `anthropic` package is importable;
2. an API key is present (`ANTHROPIC_API_KEY`);
3. a cheap probe call to the model succeeds (or `--no-probe` to skip).

Fable specifics honoured by the integration (`rse_annotations/fable.py`):

- **thinking is always on** — we omit the `thinking` parameter;
- depth via `output_config={"effort": "medium"}`;
- **refusal handling + server-side fallback on by default** — we pass
  `betas=["server-side-fallback-2026-06-01"]` and
  `fallbacks=[{"model": "claude-opus-4-8"}]`, and check `stop_reason == "refusal"`
  before reading content;
- **no assistant prefill** — we use structured `output_config.format` for the stub list;
- requires **30-day data retention** (won't run under ZDR).

Generated stubs are *scaffolding only* — they contain `# TODO: assert ...` placeholders and
property-based test ideas, never fabricated "known good" outputs, so they can't silently
bless wrong maths.

---

## 5. Package layout

```
rse_code_annotations/
├── CONCEPT.md                  # this document
├── README.md                   # quickstart
├── pyproject.toml
├── rse_annotations/
│   ├── __init__.py             # re-exports the four decorators + Runner
│   ├── annotations.py          # @functional / @mapping / @data_input / @data_output
│   ├── registry.py             # AnnotationInfo, REGISTRY, discovery helpers
│   ├── checks.py               # AST placement + docstring + I/O-success checks
│   ├── fable.py                # Claude Fable 5 stub generation (optional)
│   ├── runner.py               # orchestration + Report
│   └── cli.py                  # `python -m rse_annotations.cli run <pkg>`
├── examples/
│   └── sample_pipeline.py      # one function of each kind, correct + incorrect
└── tests/
    └── test_framework.py
```

## 6. Non-goals

- Proving mathematical correctness automatically (we *assist* review, not replace it).
- Enforcing purity at runtime (the purity check is a best-effort static lint).
- Being a general test framework — it wraps `pytest`/`unittest`, it does not replace them.
