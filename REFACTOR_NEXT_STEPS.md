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
- [ ] `analysis/__init__.py`, `analysis/static.py`, `analysis/plugins.py`
- [ ] responsible-RSE stubs in `analysis/responsible/`, based on `RESPONSIBLE_RSE_PLUGINS.md`
- [ ] `rendering.py`, `review.py`, `testing.py`, `audit.py`
- [ ] rebuild the CLI; re-export the new names in `__init__.py`
- [ ] tests for the class layer: `tests/test_object_model.py`. The 57 existing tests must still pass (`python -m pytest -q`).
- [ ] update `ARCHITECTURE.md` and republish the architecture page
- [ ] later: optionally move engine code into the classes, and retire `runner.Runner` in favour of `Audit`

Python: `/c/Users/julian.dehne/AppData/Local/Programs/Python/Python313/python.exe`.
