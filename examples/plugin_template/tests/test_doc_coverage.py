"""Acceptance tests for the exercise. Run: pytest examples/plugin_template/tests"""

import textwrap

import pytest

from rse_annotations import Audit, TargetProject
from rse_doc_coverage import DocCoverageAnalyzer


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pipeline.py").write_text(textwrap.dedent('''
        def documented(x):
            """Double x.

            Args:
                x: the value.
            """
            return 2 * x

        def half_documented(x, y):
            """Add x and y."""
            return x + y

        def bare(x):
            return x
    '''))
    return TargetProject.from_path(tmp_path)


def _run(project, **kw):
    return Audit(project, analyzers=[DocCoverageAnalyzer(**kw)]).run().result("docs")


# ---- level 1 ------------------------------------------------------------- #
def test_level1_summary(project):
    summary = [f for f in _run(project).findings if f.rule == "doc_coverage"]
    assert len(summary) == 1
    assert summary[0].evidence["coverage"] == pytest.approx(2 / 3)


def test_level1_undocumented(project):
    missing = [f for f in _run(project).findings if f.rule == "undocumented"]
    assert [f.function.rsplit(".", 1)[-1] for f in missing] == ["bare"]
    assert missing[0].severity == "warn"


def test_level1_threshold_gate(project):
    analyzer = DocCoverageAnalyzer()
    analyzer.threshold = 0.9
    result = Audit(project, analyzers=[analyzer]).run().result("docs")
    assert result.status == "fail"


def test_level1_is_a_plugin():
    from rse_annotations import default_catalog
    assert "docs" in default_catalog()   # needs `pip install -e examples/plugin_template`


# ---- level 2 ------------------------------------------------------------- #
@pytest.mark.skip(reason="level 2 -- remove this marker when you get there")
def test_level2_params(project):
    params = [f for f in _run(project).findings if f.rule == "undocumented_param"]
    assert {f.evidence.get("param") for f in params} == {"x", "y"}  # half_documented
