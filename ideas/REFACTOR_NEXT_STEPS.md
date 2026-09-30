# Object-model refactor: handoff

Branch `refactor/object-model` (local only, never pushed). It started from `main` @ `5c358d9`.

## What the user asked (2026-09-29)

1. Restructure the code to be reasonably object-oriented:
   - A **target project object** holding the path or URL of the analysed project.
   - **Analyzing**, **visualizing verdicts** and **generating tests** each behind classes.
   - Each analysis idea (maths, input/output, ...) as a **subclass of an Analyzer top class**.
   - Merge this with the plugin design in `INSPECTION_COMPONENTS.md`.
2. Update the architecture website: https://claude.ai/artifact/LqK3W97c8wyzEh2btVbrmY. The source was the job-tmp file `rse-architecture.html`; if it is gone, `Artifact read` the URL and republish with `url`.
3. Suggest more plugins on the theme **"Responsible RSE"**. Do **not implement** them. Create **stubs** in the new structure: the students in the user's "Responsible RSE" class will implement them.
   - A research agent wrote the proposals to `RESPONSIBLE_RSE_PLUGINS.md`.

## Design (names chosen by Claude; the user allowed renaming)

The old modules stay as the engine and keep their public API (tests, examples and the lni_study testbed import them). The new layer:

| New module | Class(es) | Role |
|---|---|---|
| `target.py` | `TargetProject` | path or git `url` (lazy `git clone --depth 1`), `ref`, `name`; cached `annotations()` (imports) and `static_scan()` (AST only) |
| `findings.py` | `Finding`, `AnalysisResult` | common output of every analyzer; severity info/warn/fail |
| `analysis/base.py` | `Analyzer` (ABC = plugin base), `AnnotationAnalyzer`, `StaticAnalyzer` | `name`, `description`, `when` in static/test/runtime/ci, `imports_target`, `available()`, `analyze(target)` |
| `analysis/annotated.py` | `MathAnalyzer`, `IOAnalyzer`, `ConventionAnalyzer` | wrap formula inference, the io_success check, and the placement/docstring checks |
| `analysis/static.py` | `CoverageAnalyzer`, `HazardAnalyzer` | wrap the `coverage.scan_path` results |
| `analysis/plugins.py` | `AnalyzerRegistry` | built-ins plus entry-point group `rse_annotations.analyzers` |
| `analysis/responsible/` | one stub class per responsible-RSE plugin | `available()` returns False and `analyze()` raises NotImplementedError, each with a TODO spec for students |
| `rendering.py` | `Renderer` → `TextRenderer`, `MarkdownRenderer`, `JsonRenderer` | render `AnalysisResult`s **and verdicts** |
| `review.py` | `VerdictStore`, `Reviewer` | inspection.yaml I/O plus the interactive accept/decline loop; `inspection.run_inspection` delegates here |
| `testing.py` | `TestGenerator` (`__test__ = False`), `DifferentialVerifier` | wrap `stubs` and `verify` |
| `audit.py` | `Audit`, `AuditReport` | facade: target + analyzers → results; hands out reviewer and test generator |
| `cli.py` | rebuilt on the classes | keep `--inspect/--stubs/--coverage` and their messages (tests assert them); add `--analyze`, `--list-analyzers`, URL targets |

## Status

- [x] `target.py`, `findings.py`, `analysis/base.py`, `analysis/annotated.py` (commit `5d016d5`)
- [x] `analysis/__init__.py`, `analysis/static.py`, `analysis/plugins.py` (the registry class is named `AnalyzerCatalog`)
- [x] 15 responsible-RSE stubs in `analysis/responsible/` (`reuse`, `integrity`, `safety`, `inclusion`), based on `RESPONSIBLE_RSE_PLUGINS.md`
- [x] `rendering.py`, `review.py`, `testing.py`, `audit.py`
- [x] CLI rebuilt (`--analyze`, `--list-analyzers`, `--only`, `--format`, URL targets); new names re-exported in `__init__.py`
- [x] `tests/test_object_model.py` (26 tests); 83 tests pass in total
- [x] update `ARCHITECTURE.md` and republish the architecture page
- [x] `runner.Runner` retired as a deprecated shim over `Audit` (`TargetProject.from_modules`, `Report.from_audit`); 84 tests pass (2026-09-30)
- [x] `examples/plugin_template/`: documentation-coverage exercise (skeleton + 3-level spec + acceptance tests), for the user to solve themselves as the API accessibility test (2026-09-30)
- [ ] later, optional: move engine code (`checks`, `coverage`, `stubs`) into the classes. Not needed: they are public API used by tests, examples and lni_study

## Open todos

- [ ] **Analyse EVERSE RSQKit** (https://everse.software/RSQKit/, the Research Software Quality Kit) for plugin ideas and existing work:
  - map its quality indicators and tasks onto our analyzers and the 15 Responsible-RSE stubs;
  - note tools and prior work to reuse or cite (in the stub docstrings and in `RESPONSIBLE_RSE_PLUGINS.md`);
  - list gaps, i.e. new plugin ideas.
  - The user added this on 2026-09-29 and extended it on 2026-09-30 to the whole EVERSE output (not only RSQKit), plus a workload score per stub (`difficulty`, 1 = 1 h/week ... 5 = 5 h/week). Result: `EVERSE_MAPPING.md`.
- [ ] Check the 3 items marked [unverified] in `RESPONSIBLE_RSE_PLUGINS.md` before handing the stubs to students.
- [ ] Merge `refactor/object-model` into `main` once reviewed. The user merges; never push.

Python: `/c/Users/julian.dehne/AppData/Local/Programs/Python/Python313/python.exe`.
