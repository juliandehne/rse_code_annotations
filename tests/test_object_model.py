"""The object model: TargetProject, plugins + catalog, Audit, renderers, entry points."""

import json

import pytest

from rse_annotations import (
    MODES, PHASES, RESPONSIBLE_HAZARDS, AnalysisResult, Audit, Finding, HazardStub,
    HumanCodeInspection, JsonRenderer, MarkdownRenderer, Plugin, PluginCatalog,
    TargetProject, TestGenerator, TextRenderer, default_catalog,
)
from rse_annotations.core.target import is_url
from rse_annotations.plugins.hazards.human_code_inspection import STATIC_FACETS, InspectionData

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

def test_default_catalog_has_the_inspection_plugin_and_stubs():
    cat = default_catalog(entry_points=False)
    assert cat.names()[0] == "human_code_inspection"
    assert len(cat) == 1 + len(RESPONSIBLE_HAZARDS)


def test_plugin_modes_are_the_overridden_methods():
    assert HumanCodeInspection.modes() == MODES
    assert RESPONSIBLE_HAZARDS[0].modes() == ("analyze",)


def test_catalog_offers_plugins_per_mode():
    cat = default_catalog(entry_points=False)
    assert [c.name for c in cat.for_mode("inspect")] == ["human_code_inspection"]
    assert [c.name for c in cat.for_mode("generate_tests")] == ["human_code_inspection"]
    assert len(cat.for_mode("analyze")) == len(cat)
    with pytest.raises(ValueError):
        cat.for_mode("dance")


def test_catalog_registers_a_plugin_class():
    cat = PluginCatalog()

    @cat.register
    class Countfiles(Plugin):
        name = "countfiles"

        def analyze(self, target):
            report = target.static_scan()
            return self.result([Finding("files", "info", str(report.files_scanned))])

    assert "countfiles" in cat
    assert isinstance(cat.create(["countfiles"])[0], Countfiles)


def test_catalog_rejects_bad_classes():
    cat = PluginCatalog()
    with pytest.raises(TypeError):
        cat.register(object)

    class Nameless(Plugin):
        def analyze(self, target):
            return self.result()

    class Idle(Plugin):
        name = "idle"

    with pytest.raises(ValueError):
        cat.register(Nameless)
    with pytest.raises(ValueError, match="implements none"):
        cat.register(Idle)


def test_catalog_filters_by_phase():
    cat = default_catalog(entry_points=False)
    runtime = cat.create(when=["runtime"])
    assert {a.name for a in runtime} == {"footprint", "inference_ledger"}


def test_unknown_plugin_name_is_a_clear_error():
    with pytest.raises(KeyError, match="unknown plugin"):
        default_catalog(entry_points=False).get("nope")


# --------------------------------------------------------------------------- #
# Responsible-RSE hazard stubs
# --------------------------------------------------------------------------- #

def test_stubs_are_well_formed_and_unique():
    names = [c.name for c in RESPONSIBLE_HAZARDS]
    assert len(names) == len(set(names)) == 15
    for cls in RESPONSIBLE_HAZARDS:
        assert issubclass(cls, HazardStub)
        assert cls.when in PHASES
        assert cls.description and cls.proposal.startswith("RESPONSIBLE_RSE_PLUGINS.md")
        assert cls.tier in ("A", "B", "C")
        assert "TODO" in (cls.__doc__ or "")


def test_stubs_are_skipped_not_failed(tmp_path):
    report = Audit(TargetProject.from_path(tmp_path),
                   catalog=PluginCatalog(RESPONSIBLE_HAZARDS)).run()
    assert len(report.results) == 15
    assert all(r.status == "skipped" and "student task" in r.skipped for r in report.results)
    assert report.ok


def test_calling_a_stub_directly_raises(tmp_path):
    with pytest.raises(NotImplementedError):
        RESPONSIBLE_HAZARDS[0]().analyze(TargetProject.from_path(tmp_path))


# --------------------------------------------------------------------------- #
# The human_code_inspection plugin
# --------------------------------------------------------------------------- #

def test_audit_runs_the_inspection_plugin_on_sample(tmp_path):
    _write_sample(tmp_path, "pkg_audit")
    report = Audit(TargetProject.from_path(tmp_path)).run(only=["human_code_inspection"])
    assert [r.plugin for r in report.results] == ["human_code_inspection"]
    result = report.result("human_code_inspection")
    assert isinstance(result.data, InspectionData) and result.data.formulas
    assert "eligible functions annotated" in result.findings[0].message
    assert {"coverage", "uninspected", "formula", "placement"} <= {f.rule for f in result.findings}
    assert any(f.rule == "formula" and f.function.endswith("area") for f in result.findings)
    assert json.loads(json.dumps(report.to_dict()))["target"] == tmp_path.name


def test_inspection_facets_select_the_findings(tmp_path):
    _write_sample(tmp_path, "pkg_facets")
    result = HumanCodeInspection(["math"]).analyze(TargetProject.from_path(tmp_path))
    assert {f.rule for f in result.findings} == {"formula"}
    with pytest.raises(ValueError, match="unknown facet"):
        HumanCodeInspection(["astrology"])


def test_accepted_verdict_clears_the_uninspected_finding(tmp_path):
    _write_sample(tmp_path, "pkg_uninspected")
    plugin = HumanCodeInspection(["uninspected"])
    target = TargetProject.from_path(tmp_path)
    assert any(f.rule == "uninspected" for f in plugin.analyze(target).findings)
    plugin.inspect(target, input_fn=lambda _p: "y", output_fn=lambda _m: None)
    assert not plugin.analyze(TargetProject.from_path(tmp_path)).findings


def test_static_facets_never_import(tmp_path):
    (tmp_path / "bad.py").write_text("import sys\nsys.exit(3)\ndef f(x):\n    return x * 2\n",
                                     encoding="utf-8")
    result = HumanCodeInspection(STATIC_FACETS).analyze(TargetProject.from_path(tmp_path))
    assert result.status == "pass"


def test_audit_turns_a_crash_into_a_fail(tmp_path):
    class Boom(Plugin):
        name = "boom"

        def analyze(self, target):
            raise RuntimeError("kaputt")

    report = Audit(TargetProject.from_path(tmp_path), plugins=[Boom()]).run()
    assert report.results[0].status == "fail"
    assert "kaputt" in report.results[0].findings[0].message
    assert not report.ok


# --------------------------------------------------------------------------- #
# Renderers, test generator, reviewer
# --------------------------------------------------------------------------- #

def test_renderers_cover_results(tmp_path):
    _write_sample(tmp_path, "pkg_render")
    results = Audit(TargetProject.from_path(tmp_path)).run(
        only=["human_code_inspection", "licence"]).results
    text = TextRenderer().render_results(results)
    assert "[SKIP] licence" in text and "2 plugin(s) run" in text
    md = MarkdownRenderer().render_results(results)
    assert "# Audit report" in md and "| licence | skipped |" in md
    assert "# Annotation coverage" in md
    assert json.loads(JsonRenderer().render_results(results))["results"][1]["plugin"] == "licence"


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
# Entry points
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("flag", ["--list", "--list-plugins"])
def test_cli_list_plugins(flag):
    from rse_annotations.cli import main

    msgs = []
    assert main([flag], output_fn=msgs.append) == 0
    blob = "\n".join(msgs)
    assert "human_code_inspection" in blob and "dual_use" in blob and "tier A" in blob
    assert "inspect/analyze/tests" in blob


def test_cli_analyze_json(tmp_path):
    from rse_annotations.cli import main

    _write_sample(tmp_path, "pkg_cli_analyze")
    msgs = []
    rc = main([str(tmp_path), "--analyze", "--only", "human_code_inspection,licence",
               "--format", "json"], output_fn=msgs.append)
    data = json.loads(msgs[-1])
    assert [r["plugin"] for r in data["results"]] == ["human_code_inspection", "licence"]
    assert rc == (0 if data["ok"] else 1)


def test_cli_menu_analyze_runs_every_plugin(tmp_path):
    from rse_annotations.cli import main

    _write_sample(tmp_path, "pkg_cli_menu_analyze")
    msgs = []
    answers = iter(["2"])
    main([str(tmp_path)], input_fn=lambda _p: next(answers), output_fn=msgs.append)
    blob = "\n".join(msgs)
    assert "Choose a mode:" in blob and "1) Human inspection" in blob
    assert "human_code_inspection" in blob and "[SKIP] licence" in blob


def test_cli_asks_for_a_plugin_when_several_offer_a_mode(tmp_path):
    from rse_annotations.cli import main

    class Other(Plugin):
        name = "other"
        description = "a second inspector"

        def inspect(self, target, *, input_fn=input, output_fn=print):
            output_fn("other inspected")

    _write_sample(tmp_path, "pkg_cli_choose")
    msgs = []
    answers = iter(["1", "2"])    # human inspection, then plugin 2 ("other")
    rc = main([str(tmp_path)], input_fn=lambda _p: next(answers), output_fn=msgs.append,
              catalog=PluginCatalog([HumanCodeInspection, Other]))
    assert rc == 0
    assert "Human inspection with which plugin?" in msgs and "other inspected" in msgs


def test_cli_rejects_a_plugin_without_the_mode(tmp_path):
    from rse_annotations.cli import main

    msgs = []
    rc = main([str(tmp_path), "--inspect", "--plugin", "licence"], output_fn=msgs.append)
    assert rc == 2 and "does not offer" in msgs[-1]


def test_per_plugin_entry_point_analyzes(tmp_path):
    from rse_annotations.plugins.hazards.human_code_inspection.__main__ import main

    _write_sample(tmp_path, "pkg_plugin_main")
    msgs = []
    main([str(tmp_path), "--analyze", "--format", "json"], output_fn=msgs.append)
    assert [r["plugin"] for r in json.loads(msgs[-1])["results"]] == ["human_code_inspection"]


def test_module_target_audit_matches_legacy_runner():
    import warnings
    from examples import fixtures as fx
    from rse_annotations import Runner

    target = TargetProject.from_modules("examples.sample_pipeline")
    assert target.name == "examples.sample_pipeline"
    plugin = HumanCodeInspection(["conventions", "io"], fixtures=fx.FIXTURES)
    report = Audit(target, plugins=[plugin]).run()
    placement = {f.function.rsplit(".", 1)[-1]: f.severity
                 for f in report.result("human_code_inspection").findings
                 if f.rule == "placement"}
    assert placement["impure_sum"] == "fail"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy = Runner("examples.sample_pipeline", fixtures=fx.FIXTURES).run()
    by_name = {fr.name: fr for fr in legacy.functions}
    assert [c.name for c in by_name["untidy"].checks][:2] == ["placement", "docstring"]
    assert by_name["impure_sum"].status == "fail"
    assert legacy.formulas  # the math facet's data flows through
