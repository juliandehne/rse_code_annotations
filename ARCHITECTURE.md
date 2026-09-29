# Architecture

Updated 2026-09-29 for the object-model refactor (branch `refactor/object-model`).
Arrows are taken from the real `import` statements (lazy = imported inside a function).
Mermaid renders on GitHub.

The package has two layers:

- **Object layer (new).** `TargetProject` → `Audit` → `Analyzer` subclasses → `AnalysisResult`,
  plus `Reviewer` (verdicts), `Renderer` (visualisation) and `TestGenerator` (tests).
  This is what the CLI and new code use.
- **Engine (unchanged API).** `discovery`, `checks`, `formula`, `snippets`, `coverage`,
  `inspection`, `stubs`, `verify`, `runner`. The object layer wraps them, so `tests/`,
  `examples/` and the lni_study testbed keep working.

## 1. Module dependencies

`A --> B` means *A imports B*. The graph is acyclic.

```mermaid
flowchart TB
    subgraph entry["Entry points"]
        cli["cli<br/><i>menu, --analyze, --list-analyzers</i>"]
        init["__init__<br/><i>public API</i>"]
    end

    subgraph oo["Object layer"]
        audit["audit<br/>Audit, AuditReport"]
        target["target<br/>TargetProject"]
        findings["findings<br/>Finding, AnalysisResult"]
        review["review<br/>VerdictStore, Reviewer"]
        rendering["rendering<br/>Text / Markdown / JsonRenderer"]
        testing["testing<br/>TestGenerator, DifferentialVerifier"]
        subgraph an["analysis/"]
            base["base<br/>Analyzer, AnnotationAnalyzer, StaticAnalyzer"]
            annotated["annotated<br/>Math, IO, Convention"]
            static["static<br/>Coverage, Hazard"]
            plugins["plugins<br/>AnalyzerCatalog"]
            resp["responsible/<br/>15 ResponsibleRSEStub"]
        end
    end

    subgraph engine["Engine (unchanged API)"]
        runner["runner"]
        inspection["inspection<br/>Verdict, yaml"]
        stubs["stubs"]
        coverage["coverage<br/>scan_path"]
        checks["checks"]
        formula["formula"]
        snippets["snippets"]
        discovery["discovery"]
        verify["verify"]
        registry["registry<br/>KINDS, AnnotationInfo"]
    end

    cli --> audit & target & plugins & rendering & coverage
    init --> audit & plugins & rendering

    audit --> findings & review & testing
    target --> discovery & registry
    target -. lazy .-> coverage
    review --> formula & inspection & snippets & registry
    rendering --> coverage & findings & inspection
    testing --> stubs & verify

    base --> findings & registry
    annotated --> base & checks & formula & findings
    static --> base & coverage & findings
    plugins --> annotated & static & base
    plugins -. lazy .-> resp
    resp --> base
    inspection -. lazy .-> review

    runner --> checks & discovery & formula & snippets & registry
    coverage --> checks & discovery & registry
    stubs --> formula & registry
```

Two import cycles are avoided with lazy imports: `inspection.run_inspection` now delegates
to `review.Reviewer`, and `plugins.default_catalog` loads `responsible/` on demand.

## 2. Class hierarchy (the plugin design)

Each analysis idea is a subclass of `Analyzer`. The base class *is* the plugin contract:
third-party packages register subclasses under the entry-point group
`rse_annotations.analyzers`, and `AnalyzerCatalog` finds them next to the built-ins.

```mermaid
classDiagram
    direction TB
    class TargetProject {
        +path: Path?
        +url: str?
        +ref: str?
        +name: str
        +root: Path  «lazy git clone»
        +parse(spec)$
        +from_path(p)$ / from_url(u)$
        +annotations() list~AnnotationInfo~
        +static_scan() CoverageReport
        +output_path(name) Path
    }
    class Analyzer {
        <<abstract>>
        +name: str
        +description: str
        +when: static|test|runtime|ci
        +imports_target: bool
        +available() bool
        +unavailable_reason() str
        +analyze(target)* AnalysisResult
    }
    class AnnotationAnalyzer {
        <<abstract>>
        +kinds
        +analyze_one(info)* list~Finding~
    }
    class StaticAnalyzer {
        <<abstract>>
        +analyze_scan(report)* AnalysisResult
    }
    class ResponsibleRSEStub {
        <<abstract>>
        +tier: A|B|C
        +effort, proposal, hooks, tools
        available() = False
    }
    Analyzer <|-- AnnotationAnalyzer
    Analyzer <|-- StaticAnalyzer
    Analyzer <|-- ResponsibleRSEStub
    AnnotationAnalyzer <|-- MathAnalyzer : math
    AnnotationAnalyzer <|-- IOAnalyzer : io
    AnnotationAnalyzer <|-- ConventionAnalyzer : conventions
    StaticAnalyzer <|-- CoverageAnalyzer : coverage
    StaticAnalyzer <|-- HazardAnalyzer : hazards

    class Finding {
        +rule, severity, message
        +function?, location?, data
    }
    class AnalysisResult {
        +analyzer: str
        +findings: list~Finding~
        +skipped: str?
        +status: pass|warn|fail|skipped
        +ok: bool
    }
    AnalysisResult *-- Finding

    class AnalyzerCatalog {
        +register(cls)
        +load_entry_points()
        +names() / get(name) / classes()
        +create(names, when) list~Analyzer~
    }
    class Audit {
        +target: TargetProject
        +select(only, when)
        +run(only, when) AuditReport
        +reviewer(**io) Reviewer
        +test_generator(out_dir) TestGenerator
    }
    class AuditReport {
        +results: list~AnalysisResult~
        +ok: bool
        +to_dict()
    }
    class Renderer {
        <<abstract>>
        +render_results(results) str
        +render_verdicts(verdicts) str
    }
    Renderer <|-- TextRenderer
    Renderer <|-- MarkdownRenderer
    Renderer <|-- JsonRenderer
    class VerdictStore {
        +load() / save() / summary()
    }
    class Reviewer {
        +review(infos) list~Verdict~
    }
    class TestGenerator {
        +stub_files() / write()
    }
    class DifferentialVerifier {
        +check(candidate, reference, gen)
    }

    Audit --> TargetProject
    Audit --> AnalyzerCatalog
    AnalyzerCatalog ..> Analyzer : instantiates
    Analyzer ..> TargetProject : analyze(target)
    Analyzer ..> AnalysisResult : returns
    Audit ..> AuditReport : creates
    AuditReport *-- AnalysisResult
    Audit ..> Reviewer
    Audit ..> TestGenerator
    Reviewer --> VerdictStore
    Renderer ..> AnalysisResult
    Renderer ..> VerdictStore : verdicts
```

The three responsibilities the refactor asked for:

| Responsibility | Class(es) | Wraps (engine) | Output |
|---|---|---|---|
| Analysing code | `Analyzer` subclasses, run by `Audit` | `checks`, `formula`, `coverage` | `AnalysisResult` / `AuditReport` |
| Visualising verdicts | `Reviewer` + `VerdictStore`; `Renderer` subclasses | `inspection` | `inspection.yaml`, text / markdown / JSON |
| Generating tests | `TestGenerator`, `DifferentialVerifier` | `stubs`, `verify` | `tests/test_*.py`, `DiffResult` |

`Audit.run()` never crashes on one analyzer:

- an unavailable analyzer (a missing optional dependency, or a stub) is reported as **skipped** with its reason;
- an exception is turned into a **fail** finding (`analyzer_error`).

## 3. Writing a plugin

```python
from rse_annotations import StaticAnalyzer, Finding

class TodoCounter(StaticAnalyzer):
    name = "todo_count"
    description = "counts unannotated candidate functions"
    when = "static"

    def analyze_scan(self, report):
        n = sum(1 for r in report.records if r.eligible and not r.kind)
        return self.result([Finding("unannotated", "info", f"{n} candidates")])
```

Register it in the plugin package's `pyproject.toml`:

```toml
[project.entry-points."rse_annotations.analyzers"]
todo_count = "my_pkg.checks:TodoCounter"
```

Then run it with `python -m rse_annotations.cli src --analyze --only todo_count`. To check that it is found, use `--list-analyzers`.

## 4. Responsible-RSE stubs (course tasks)

`analysis/responsible/` holds 15 stubs from `RESPONSIBLE_RSE_PLUGINS.md`. They are listed by
`--list-analyzers` and are *skipped* in every audit until implemented. Each docstring is the
task spec ("TODO (Tier X, effort)"), and `_stub.py` explains how to turn one into a working analyzer.

| Module (question) | Analyzer `name` | Tier | when |
|---|---|---|---|
| `reuse` — can others legally reuse it? | `licence`, `data_terms` | A | static |
| | `archival` | C | static |
| `integrity` — are the results trustworthy? | `silent_failures`, `constants`, `llm_disclosure` | A | static |
| | `leakage` | B | static |
| | `inference_ledger` | B | runtime |
| `safety` — can it harm? | `security` | A | static |
| | `purpose_retention` | B | static |
| | `dual_use` | C | static |
| `inclusion` — is it inclusive and sustainable? | `fairness` | B | test |
| | `figure_accessibility` | B | static |
| | `footprint` | B | runtime |
| | `inclusive_language` | C | static |

Tier A = a static check doable in one session; B = needs runtime hooks or a library; C = research-grade.

**Open:** analyse [EVERSE RSQKit](https://everse.software/RSQKit/) for ideas and existing work
to map onto these stubs (see `REFACTOR_NEXT_STEPS.md`).

## 5. Engine data classes (unchanged)

| Module | Produces | Persisted as |
|---|---|---|
| `inspection` | `Verdict` | `inspection.yaml` |
| `stubs` | `StubFile` | `test_*.py` stubs that `skip()` until filled in |
| `coverage` | `CoverageReport` → `FunctionRecord` → `Hazard` | `annotation_coverage.md` |
| `runner` | `Report` (legacy batch path, superseded by `Audit`) | text / JSON |
| `verify` | `DiffResult` | — (in memory, for tests) |

Only the standard library is required (`dependencies = []`). SymPy and latexify are loaded lazily inside `formula`.

## 6. Consumers (outside the package)

```mermaid
flowchart LR
    tests["tests/ (83 tests)"] --> pkg
    examples["examples/sample_pipeline.py"] --> pkg
    demo["scripts/demo_lni_testbed.py"] -- "python -m rse_annotations.cli" --> pkg
    lni["lni_study<br/>branch feat/rse-code-annotations"] -- "pip install -e" --> pkg
    students["Responsible-RSE course<br/>(implements stubs)"] -- "entry points / PRs" --> pkg
    pkg(["rse_annotations"])
```
