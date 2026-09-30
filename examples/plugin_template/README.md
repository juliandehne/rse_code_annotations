# Exercise: write a documentation-coverage plugin

The test run for the plugin API: can someone who has never seen the code base add
a plugin in an afternoon? Do it exactly the way a student would, and note where
you get stuck (see *Friction log* below).

## Steps

1. Install the framework and this plugin, both editable:
   ```
   pip install -e .                          # from rse_code_annotations/
   pip install -e examples/plugin_template
   ```
2. Check that it is picked up: `python -m rse_annotations --list`
   should list `docs`.
3. Implement `DocCoverage.analyze` in `rse_doc_coverage/__init__.py`,
   one level at a time (the class docstring has the spec).
4. Run the acceptance tests: `pytest examples/plugin_template/tests`.
   Level 2 is skipped until you remove its `skip` marker.
5. Try it on real code:
   ```
   python -m rse_annotations <some project> --analyze --only docs
   python -m rse_annotations <some project> --analyze --only docs --format json
   ```

## What you need to know (and nothing more)

| You get | From |
|---|---|
| `Plugin` | subclass it and implement `analyze(target)` (the *hazard analysis* mode) |
| `target.static_scan()` | the parsed code base (never imported), a `CoverageReport` |
| `report.eligible` | the functions that count, as `FunctionRecord`s |
| `rec.has_docstring`, `rec.module`, `rec.qualname`, `rec.location`, `rec.file` | per function |
| `Finding(rule, severity, message, function=, location=, evidence=)` | what you report; severity is `info`, `warn` or `fail` |
| `self.result(findings, data=...)` | wraps them into an `AnalysisResult` |

The renderers, the CLI, the JSON output and the CI exit code come for free.

## Friction log

Write down, per level: time spent, what you had to look up outside this README,
and every error message that did not tell you what to do. These notes are how we
decide the difficulty scores of the student stubs (1 = 1 h/week ... 5 = 5 h/week).

| Level | Time | Looked up | Confusing |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
