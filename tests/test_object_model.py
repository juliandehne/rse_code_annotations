"""The object model: TargetProject, analyzers + catalog, Audit, renderers, stubs."""

import json

import pytest

from rse_annotations import (
    RESPONSIBLE_ANALYZERS, Analyzer, AnalysisResult, AnalyzerCatalog, Audit,
    CoverageAnalyzer, Finding, JsonRenderer, MarkdownRenderer, MathAnalyzer,
    ResponsibleRSEStub, StaticAnalyzer, TargetProject, TestGenerator, TextRenderer,
    default_catalog,
)
from rse_annotations.analysis.base import PHASES
from rse_annotations.target import is_url

from test_framework import _write_sample


# --------------------------------------------------------------------------- #
# TargetProject
# --------------------------------------------------------------------------- #

def test_target_needs_path_or_url():
    with pytest.raises(ValueError):
        TargetProject()


@pytest.mark.parametrize("spec,remote", [
    ("https://github.com/org/repo.git", True),
    ("git@github.com:org/repo.git", True),
    ("src/pkg", False),
    (".", False),
])
def test_target_parse_detects_urls(spec, remote):
    assert is_url(spec) is remote
    assert TargetProject.parse(spec).is_remote is remote


def test_target_url_name_is_repo_name():
    assert TargetProject.from_url("https://github.com/org/my-repo.git").name == "my-repo"


def test_target_local_paths(tmp_path):
    t = TargetProject.from_path(tmp_path)
    assert t.root == tmp_path
    assert t.output_path("inspection.yaml") == tmp_path / "inspection.yaml"


# --------------------------------------------------------------------------- #
# Findings
# --------------------------------------------------------------------------- #

def test_finding_rejects_unknown_severity():
    with pytest.raises(ValueError):
        Finding("r", "catastrophic", "m")


def test_result_status_is_worst_severity():
    info, warn, fail = (Finding("r", s, "m") for s in ("info", "warn", "fail"))
    assert AnalysisResult("a", [info]).status == "pass"
    assert AnalysisResult("a", [info, warn]).status == "warn"
    assert AnalysisResult("a", [warn, fail]).status == "fail"
    assert AnalysisResult("a", [], skipped="why").status == "skipped"
    assert not AnalysisResult("a", [fail]).ok


# --------------------------------------------------------------------------- #
# Catalog and plugins
# --------------------------------------------------------------------------- #

def test_default_catalog_has_builtins_and_stubs():
    cat = default_catalog(plugins=False)
    assert {"coverage", "hazards", "conventions", "math", "io"} <= set(cat.names())
    assert len(cat) == 5 + len(RESPONSIBLE_ANALYZERS)


def test_catalog_registers_a_plugin_class():
    cat = AnalyzerCatalog()

    @cat.register
    class Countfiles(StaticAnalyzer):
        name = "countfiles"

        def analyze_scan(self, report):
            return self.result([Finding("files", "info", str(report.files_scanned))])

    assert "countfiles" in cat
    assert isinstance(cat.create(["countfiles"])[0], Countfiles)


def test_catalog_rejects_bad_classes():
    cat = AnalyzerCatalog()
    with pytest.raises(TypeError):
        cat.register(object)

    class Nameless(StaticAnalyzer):
        def analyze_scan(self, report):
            return self.result()

    with pytest.raises(ValueError):
        cat.register(Nameless)


def test_catalog_filters_by_phase():
    cat = default_catalog(plugins=False)
    assert all(a.when == "test" for a in cat.create(when=["test"]))


def test_unknown_analyzer_name_is_a_clear_error():
    with pytest.raises(KeyError, match="unknown analyzer"):
        default_catalog(plugins=False).get("nope")


# --------------------------------------------------------------------------- #
# Responsible-RSE stubs
# --------------------------------------------------------------------------- #

def test_stubs_are_well_formed_and_unique():
    names = [c.name for c in RESPONSIBLE_ANALYZERS]
    assert len(names) == len(set(names)) == 15
    for cls in RESPONSIBLE_ANALYZERS:
        assert issubclass(cls, ResponsibleRSEStub)
        assert cls.when in PHASES
        assert cls.description and cls.proposal.startswith("RESPONSIBLE_RSE_PLUGINS.md")
        assert cls.tier in ("A", "B", "C")
        assert "TODO" in (cls.__doc__ or "")


def test_stubs_are_skipped_not_failed(tmp_path):
    report = Audit(TargetProject.from_path(tmp_path),
                   catalog=AnalyzerCatalog(RESPONSIBLE_ANALYZERS)).run()
    assert len(report.results) == 15
    assert all(r.status == "skipped" and "student task" in r.skipped for r in report.results)
    assert report.ok


def test_calling_a_stub_directly_raises(tmp_path):
    with pytest.raises(NotImplementedError):
        RESPONSIBLE_ANALYZERS[0]().analyze(TargetProject.from_path(tmp_path))


# --------------------------------------------------------------------------- #
# Audit over a real sample
# --------------------------------------------------------------------------- #

def test_audit_runs_builtins_on_sample(tmp_path):
    _write_sample(tmp_path, "pkg_audit")
    report = Audit(TargetProject.from_path(tmp_path)).run(only=["coverage", "math"])
    assert [r.analyzer for r in report.results] == ["coverage", "math"]
    cov = report.result("coverage")
    assert "eligible functions annotated" in cov.findings[0].message
    math = report.result("math")
    assert any(f.function == "area" for f in math.findings)
    assert json.loads(json.dumps(report.to_dict()))["target"] == tmp_path.name


def test_audit_turns_a_crash_into_a_fail(tmp_path):
    class Boom(Analyzer):
        name = "boom"

        def analyze(self, target):
            raise RuntimeError("kaputt")

    report = Audit(TargetProject.from_path(tmp_path), analyzers=[Boom()]).run()
    assert report.results[0].status == "fail"
    assert "kaputt" in report.results[0].findings[0].message
    assert not report.ok


def test_math_analyzer_skips_without_functional(tmp_path):
    (tmp_path / "plain.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    result = MathAnalyzer().analyze(TargetProject.from_path(tmp_path))
    assert result.status == "skipped"


def test_coverage_analyzer_never_imports(tmp_path):
    (tmp_path / "bad.py").write_text("import sys\nsys.exit(3)\ndef f(x):\n    return x * 2\n",
                                     encoding="utf-8")
    result = CoverageAnalyzer().analyze(TargetProject.from_path(tmp_path))
    assert result.status == "pass"


# --------------------------------------------------------------------------- #
# Renderers, test generator, reviewer
# --------------------------------------------------------------------------- #

def test_renderers_cover_results(tmp_path):
    _write_sample(tmp_path, "pkg_render")
    results = Audit(TargetProject.from_path(tmp_path)).run(only=["coverage", "licence"]).results
    text = TextRenderer().render_results(results)
    assert "[SKIP] licence" in text and "2 analyzer(s) run" in text
    md = MarkdownRenderer().render_results(results)
    assert md.startswith("# Audit report") and "| licence | skipped |" in md
    assert json.loads(JsonRenderer().render_results(results))["ok"] is True


def test_reviewer_and_verdict_rendering(tmp_path):
    _write_sample(tmp_path, "pkg_review")
    audit = Audit(TargetProject.from_path(tmp_path))
    verdicts = audit.reviewer(input_fn=lambda _p: "y", output_fn=lambda _m: None).review(
        audit.target.annotations())
    assert (tmp_path / "inspection.yaml").exists()
    assert "1 accepted" in TextRenderer().render_verdicts(verdicts)
    assert json.loads(JsonRenderer().render_verdicts(verdicts))["summary"]["accepted"] == 1


def test_test_generator_writes_into_target(tmp_path):
    _write_sample(tmp_path, "pkg_gen")
    files = TestGenerator(TargetProject.from_path(tmp_path)).write(lambda _m: None)
    assert files and all(f.path.parent == tmp_path / "tests" for f in files)


# --------------------------------------------------------------------------- #
# CLI additions
# --------------------------------------------------------------------------- #

def test_cli_list_analyzers():
    from rse_annotations.cli import main

    msgs = []
    assert main(["--list-analyzers"], output_fn=msgs.append) == 0
    blob = "\n".join(msgs)
    assert "coverage" in blob and "dual_use" in blob and "tier A" in blob


def test_cli_analyze_json(tmp_path):
    from rse_annotations.cli import main

    _write_sample(tmp_path, "pkg_cli_analyze")
    msgs = []
    rc = main([str(tmp_path), "--analyze", "--only", "coverage,hazards", "--format", "json"],
              output_fn=msgs.append)
    data = json.loads(msgs[-1])
    assert rc == 0 and [r["analyzer"] for r in data["results"]] == ["coverage", "hazards"]


def test_module_target_audit_matches_legacy_runner():
    import warnings
    from examples import fixtures as fx
    from rse_annotations import (Audit, ConventionAnalyzer, IOAnalyzer, Runner,
                                 TargetProject)

    target = TargetProject.from_modules("examples.sample_pipeline")
    assert target.name == "examples.sample_pipeline"
    report = Audit(target, analyzers=[ConventionAnalyzer(), IOAnalyzer(fx.FIXTURES)]).run()
    placement = {f.function.rsplit(".", 1)[-1]: f.severity
                 for f in report.result("conventions").findings if f.rule == "placement"}
    assert placement["impure_sum"] == "fail"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy = Runner("examples.sample_pipeline", fixtures=fx.FIXTURES).run()
    by_name = {fr.name: fr for fr in legacy.functions}
    assert [c.name for c in by_name["untidy"].checks][:2] == ["placement", "docstring"]
    assert by_name["impure_sum"].status == "fail"
    assert legacy.formulas  # math analyzer data flows through
