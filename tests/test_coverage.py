"""Tests for the static (AST) coverage scan -- no import of the target, no LLM."""

from __future__ import annotations

import os
import sys
import textwrap

import pytest

# Make the project root importable when run from anywhere.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rse_annotations.coverage import (  # noqa: E402
    HAZARD_PARENT,
    HAZARDS,
    render_coverage_markdown,
    render_coverage_text,
    scan_path,
)


def _write(tmp_path, name: str, src: str):
    path = tmp_path / name
    path.write_text(textwrap.dedent(src), encoding="utf-8")
    return path


SAMPLE = """
    from pathlib import Path

    import rse_annotations
    from rse_annotations import data_input, functional as pure

    @pure
    def area(r):
        return 3.14159 * r ** 2

    @data_input(fields={"path": "the csv to read"})
    def load(path):
        "Read it."
        return Path(path).read_text()

    @rse_annotations.data_output
    def dump(rows, path):
        "Write it."
        Path(path).write_text(str(rows))

    def normalise(x, y):          # candidate: @functional (pure arithmetic)
        return (x - y) / (x + y)

    def to_records(frame):        # candidate: @mapping
        return [dict(row) for row in frame.itertuples()]

    def save_report(df, path):    # candidate: @data_output
        df.to_csv(path)

    def read_config(path):        # candidate: @data_input
        return Path(path).read_text()

    def main():                   # not a candidate: procedural glue
        print("hi")

    class Box:
        def __init__(self, v):    # not eligible: dunder
            self.v = v

        def scaled(self, k):      # candidate: @functional (a method still counts)
            return self.v * k

    def outer(a):
        def inner(b):             # not eligible: nested
            return b + 1
        return inner(a)
"""


def _index(report):
    return {r.qualname: r for r in report.records}


def test_scan_finds_existing_annotations_without_importing(tmp_path):
    # numpy/pandas are NOT installed for this module and Path.read_text on a fake
    # file would explode -- but nothing is imported or executed, so it doesn't matter.
    _write(tmp_path, "sample.py", SAMPLE)
    report = scan_path(tmp_path)
    by_name = _index(report)

    assert by_name["area"].kind == "functional"        # aliased import (functional as pure)
    assert by_name["load"].kind == "data_input"        # called form with fields=
    assert by_name["dump"].kind == "data_output"       # qualified @rse_annotations.data_output
    assert report.counts_by_kind() == {
        "functional": 1, "mapping": 0, "data_input": 1, "data_output": 1,
    }


def test_scan_works_on_a_module_that_cannot_be_imported(tmp_path):
    _write(tmp_path, "broken.py", """
        import a_package_that_does_not_exist  # would raise on import
        import sys
        sys.exit(0)                            # ...and then kill the process

        def halve(x):
            return x / 2
    """)
    report = scan_path(tmp_path)
    assert [r.name for r in report.records] == ["halve"]
    assert report.records[0].suggested == "functional"


def test_syntax_error_is_recorded_not_raised(tmp_path):
    _write(tmp_path, "bad.py", "def oops(:\n")
    report = scan_path(tmp_path)
    assert len(report.parse_errors) == 1
    assert "bad.py" in report.parse_errors[0][0]


def test_candidates_are_suggested_by_body_shape(tmp_path):
    _write(tmp_path, "sample.py", SAMPLE)
    by_name = _index(scan_path(tmp_path))

    assert by_name["normalise"].suggested == "functional"
    assert by_name["normalise"].confidence == "high"
    assert by_name["to_records"].suggested == "mapping"
    assert by_name["save_report"].suggested == "data_output"
    assert by_name["read_config"].suggested == "data_input"
    assert by_name["Box.scaled"].suggested == "functional"


def test_procedural_glue_is_not_a_candidate(tmp_path):
    _write(tmp_path, "sample.py", SAMPLE)
    by_name = _index(scan_path(tmp_path))

    main = by_name["main"]
    assert main.eligible and main.suggested is None
    assert "procedural" in main.reason


def test_dunders_and_nested_functions_are_not_eligible(tmp_path):
    _write(tmp_path, "sample.py", SAMPLE)
    by_name = _index(scan_path(tmp_path))

    assert by_name["Box.__init__"].eligible is False
    assert by_name["outer.inner"].eligible is False
    # ...and therefore not in the coverage denominator
    assert all(r.eligible for r in scan_path(tmp_path).eligible)


def test_annotated_functions_are_never_candidates(tmp_path):
    _write(tmp_path, "sample.py", SAMPLE)
    report = scan_path(tmp_path)
    assert not any(c.annotated for c in report.candidates)
    assert report.coverage == pytest.approx(3 / len(report.eligible))


def test_in_memory_conversions_are_not_mistaken_for_file_io(tmp_path):
    """``json.loads`` / ``df.to_dict`` look like I/O to a naive prefix rule."""
    _write(tmp_path, "conv.py", """
        import json

        def parse(raw):
            return json.loads(raw)

        def as_dict(df):
            return df.to_dict()
    """)
    by_name = _index(scan_path(tmp_path))
    assert by_name["parse"].suggested == "mapping"
    assert by_name["as_dict"].suggested == "mapping"


def test_open_is_classified_by_its_mode_not_its_name(tmp_path):
    """``open(p, "w")`` is a write. A name-only rule would call it a read."""
    _write(tmp_path, "io.py", """
        def slurp(p):
            with open(p) as fh:
                return fh.read()

        def spew(p, text):
            with open(p, "w") as fh:
                fh.write(text)
            return p

        def append_line(p, text):
            with open(p, mode="a") as fh:
                fh.write(text)
            return p
    """)
    by_name = _index(scan_path(tmp_path))
    assert by_name["slurp"].suggested == "data_input"
    assert by_name["spew"].suggested == "data_output"
    assert by_name["spew"].confidence == "high"
    assert by_name["append_line"].suggested == "data_output"


def test_generic_write_is_reported_but_not_with_high_confidence(tmp_path):
    _write(tmp_path, "log.py", """
        def emit(handle, msg):
            handle.write(msg)
            return msg
    """)
    rec = _index(scan_path(tmp_path))["emit"]
    assert rec.suggested == "data_output"
    assert rec.confidence == "medium"   # could be a logger, not a file


def test_test_modules_are_excluded_from_the_scan(tmp_path):
    _write(tmp_path, "test_thing.py", "def test_x():\n    assert True\n")
    _write(tmp_path, "conftest.py", "def fixture_helper():\n    return 1\n")
    _write(tmp_path, "real.py", "def double(x):\n    return x * 2\n")
    report = scan_path(tmp_path)
    assert [r.name for r in report.records] == ["double"]


def test_renderers_produce_the_table_and_the_worklist(tmp_path):
    _write(tmp_path, "sample.py", SAMPLE)
    report = scan_path(tmp_path)

    text = render_coverage_text(report)
    assert "By annotation kind" in text
    assert "@functional" in text and "Candidates for annotation" in text

    md = render_coverage_markdown(report)
    assert md.startswith("# Annotation coverage")
    assert "| `@data_output` |" in md
    assert "`normalise`" in md          # a candidate
    assert "`main`" in md               # listed under "Not candidates"


def test_cli_coverage_writes_a_report_without_importing(tmp_path):
    from rse_annotations.cli import main as cli_main

    _write(tmp_path, "broken.py", """
        import a_package_that_does_not_exist

        def halve(x):
            return x / 2
    """)
    msgs = []
    rc = cli_main([str(tmp_path), "--coverage"], output_fn=msgs.append)
    assert rc == 0
    out = tmp_path / "annotation_coverage.md"
    assert out.exists()
    assert "halve" in out.read_text(encoding="utf-8")
    # no import was attempted, so discovery never warned about the broken module
    assert not any("could not import" in m for m in msgs)


def test_cli_menu_option_three_runs_coverage(tmp_path):
    from rse_annotations.cli import main as cli_main

    _write(tmp_path, "sample.py", SAMPLE)
    answers = iter(["3"])
    rc = cli_main(
        [str(tmp_path)],
        input_fn=lambda _p: next(answers),
        output_fn=lambda _m: None,
    )
    assert rc == 0
    assert (tmp_path / "annotation_coverage.md").exists()


# --------------------------------------------------------------------------- #
# Audit hazards -- the second, orthogonal axis (see PROPOSED_ANNOTATIONS.md).
#
# Every body below is modelled on one found in the `lni_study` testbed; the
# false-positive tests in particular each pin a real miss the first run made.
# --------------------------------------------------------------------------- #

def _hazards(rec):
    return {h.kind: h for h in rec.hazards}


def test_the_hazard_axis_specialises_the_dataflow_one(tmp_path):
    """A hazard is a *specialisation* of a dataflow kind, not a competitor to it."""
    assert HAZARD_PARENT["stochastic"] == "functional"    # pure *given the seed*
    assert HAZARD_PARENT["statistical"] == "functional"
    assert HAZARD_PARENT["model_call"] == "data_input"    # data enters from a model
    assert HAZARD_PARENT["human_input"] == "data_input"   # ... or from a person
    assert HAZARD_PARENT["unit_of_analysis"] == "mapping"
    assert HAZARD_PARENT["external_tool"] is None         # the process itself is left
    assert set(HAZARD_PARENT) == set(HAZARDS)


def test_model_call_is_detected_and_is_not_called_no_io(tmp_path):
    """The LLM call is the study's raw-data boundary; dataflow alone calls it "no I/O"."""
    _write(tmp_path, "llm.py", """
        from openai import OpenAI

        def classify_paper(client, text):
            resp = client.chat.completions.create(model="gpt-4", messages=[])
            return resp.choices[0].message.content
    """)
    rec = _index(scan_path(tmp_path))["classify_paper"]
    assert "model_call" in rec.hazard_kinds
    assert rec.hazard("model_call").confidence == "high"
    assert "language model" in rec.hazard("model_call").reason


def test_human_coded_data_is_a_data_input_of_its_own_kind(tmp_path):
    """The sibling of ``@model_call``: this datum was produced by a *person*.

    Modelled on ``compute_icr.load_coders`` and ``build_goldstandard.py:80``, which read
    the coders' ``coding_<username>.csv`` files.
    """
    _write(tmp_path, "icr.py", """
        import pandas as pd

        def load_coders(goldstandard_dir):
            frames = {}
            for path in goldstandard_dir.glob("coding_*.csv"):
                frames[path.stem] = pd.read_csv(path)
            return frames
    """)
    rec = _index(scan_path(tmp_path))["load_coders"]
    haz = rec.hazard("human_input")
    assert haz is not None and haz.confidence == "high"
    assert "coding_*.csv" in haz.reason
    assert "inter-coder reliability" in haz.reason


def test_the_models_own_output_is_not_human_input(tmp_path):
    """The token "annotation" means the *machine's* answer in this codebase.

    ``annotations_<tag>_checkpoint.csv`` is written by the LLM pass; ``coding_*.csv`` is
    written by the coders. Keying human provenance on "annotation" would be exactly
    backwards, so nothing does.
    """
    _write(tmp_path, "resume.py", """
        import pandas as pd

        def load_annotation_checkpoint(run_dir, tag):
            return pd.read_csv(run_dir / f"annotations_{tag}_checkpoint.csv")
    """)
    rec = _index(scan_path(tmp_path))["load_annotation_checkpoint"]
    assert "human_input" not in rec.hazard_kinds


def test_prose_about_the_goldstandard_is_not_evidence_of_it(tmp_path):
    """A sentence mentioning the coders is not a coder file.

    The first run flagged three functions on their argparse ``help=`` text
    (``filter_positives.py:58``, ``narrow_categories.py:317``). A filename is evidence
    about where data came from; a description of it is exactly the prose the hazard axis
    exists to stop trusting.
    """
    _write(tmp_path, "cli.py", """
        import argparse
        import pandas as pd

        def main():
            ap = argparse.ArgumentParser()
            ap.add_argument("--pool", help="Keep only positives as the goldstandard pool.")
            args = ap.parse_args()
            return pd.read_csv(args.pool)
    """)
    rec = _index(scan_path(tmp_path))["main"]
    assert "human_input" not in rec.hazard_kinds


def test_a_human_source_that_reads_nothing_is_not_an_input(tmp_path):
    """``@human_input`` refines ``@data_input``: something has to come *in*."""
    _write(tmp_path, "paths.py", """
        def coding_path(root, user):
            return root / f"coding_{user}.csv"
    """)
    rec = _index(scan_path(tmp_path))["coding_path"]
    assert "human_input" not in rec.hazard_kinds


def test_shelling_out_makes_the_tool_part_of_the_method(tmp_path):
    """Modelled on ``pipeline_menu.py:478`` / ``pool_manager.py:173``.

    The computation leaves the process, so the binary and its version are as much a part
    of the method as the code that calls it -- and the dataflow axis cannot see that at
    all: ``subprocess.run`` reads no file and writes none.
    """
    _write(tmp_path, "runner.py", """
        import subprocess

        def run_step(cmd, env, repo_root):
            completed = subprocess.run(cmd, env=env, cwd=str(repo_root))
            return completed.returncode
    """)
    rec = _index(scan_path(tmp_path))["run_step"]
    haz = rec.hazard("external_tool")
    assert haz is not None and haz.confidence == "high"
    assert "subprocess.run" in haz.reason and "version" in haz.reason


def test_shell_true_is_called_out_separately(tmp_path):
    _write(tmp_path, "runner.py", """
        import subprocess

        def convert(path):
            return subprocess.check_output(f"pdftotext {path} -", shell=True)
    """)
    haz = _index(scan_path(tmp_path))["convert"].hazard("external_tool")
    assert "shell=True" in haz.reason


def test_a_local_helper_named_run_is_not_a_shell_out(tmp_path):
    """``run`` and ``call`` are too common as bare names to be evidence of anything."""
    _write(tmp_path, "steps.py", """
        def run_all(steps, ctx):
            return [run(s, ctx) for s in steps]
    """)
    rec = _index(scan_path(tmp_path))["run_all"]
    assert "external_tool" not in rec.hazard_kinds


def test_the_two_provenance_hazards_travel_up_the_call_graph(tmp_path):
    """A caller of a shell-out or of human-coded data inherits the hazard."""
    _write(tmp_path, "chain.py", """
        import subprocess
        import pandas as pd

        def load_coders(d):
            return [pd.read_csv(p) for p in d.glob("coding_*.csv")]

        def render_report(path):
            return subprocess.run(["quarto", "render", str(path)]).returncode

        def main(d, path):
            coders = load_coders(d)
            render_report(path)
            return coders
    """)
    recs = _index(scan_path(tmp_path))
    main = recs["main"]
    for kind in ("human_input", "external_tool"):
        haz = main.hazard(kind)
        assert haz is not None and haz.indirect
    # The shortlist still names the function that does the dangerous thing, not `main`.
    assert not recs["load_coders"].hazard("human_input").indirect


def test_a_seeded_rng_is_stochastic_but_checkable(tmp_path):
    _write(tmp_path, "sampling.py", """
        import random

        def stratified_sample(papers, seed):
            rng = random.Random(seed)
            rng.shuffle(papers)
            return papers[:10]
    """)
    rec = _index(scan_path(tmp_path))["stratified_sample"]
    haz = rec.hazard("stochastic")
    assert haz is not None
    assert "seed" in haz.reason and "pure given the seed" in haz.reason


def test_an_unseeded_rng_is_the_hard_failure(tmp_path):
    """No seed parameter means the sample can never be regenerated."""
    _write(tmp_path, "sampling.py", """
        import random

        def pick(papers):
            return random.sample(papers, 10)
    """)
    haz = _index(scan_path(tmp_path))["pick"].hazard("stochastic")
    assert "no seed" in haz.reason
    assert haz.confidence == "high"


def test_retry_backoff_jitter_is_not_a_reproducibility_hazard(tmp_path):
    """Jitter in a sleep interval cannot change a finding.

    Modelled on ``annotate_lni.py:348``. Without this rule the retry helper of every
    API client is flagged ``stochastic`` -- and that false positive then *propagates*
    up the call graph into the functions that do matter.
    """
    _write(tmp_path, "retry.py", """
        import random, time

        def _complete_with_retries(client, messages):
            for attempt in range(5):
                try:
                    return client.chat.completions.create(messages=messages)
                except Exception:
                    backoff = 2 ** attempt
                    wait_s = backoff + backoff * 0.25 * random.random()
                    time.sleep(wait_s)
            raise RuntimeError("gave up")

        def classify(client, text):
            return _complete_with_retries(client, [text])
    """)
    by_name = _index(scan_path(tmp_path))
    assert "stochastic" not in by_name["_complete_with_retries"].hazard_kinds
    assert "model_call" in by_name["_complete_with_retries"].hazard_kinds
    # ...and the false positive did not propagate to the caller either
    assert "stochastic" not in by_name["classify"].hazard_kinds


def test_a_statistic_via_a_library_call_must_be_pinned(tmp_path):
    _write(tmp_path, "icr.py", """
        import krippendorff
        from sklearn.metrics import cohen_kappa_score

        def compute_dimension_icr(a, b):
            return {
                "alpha": krippendorff.alpha(reliability_data=[a, b]),
                "kappa": cohen_kappa_score(a, b),
            }
    """)
    haz = _index(scan_path(tmp_path))["compute_dimension_icr"].hazard("statistical")
    assert haz.confidence == "high"
    assert "reference implementation" in haz.reason


def test_a_file_boundary_named_after_a_statistic_is_not_a_statistic(tmp_path):
    """``write_icr_outputs`` moves the number around; it does not compute it."""
    _write(tmp_path, "icr_io.py", """
        import pandas as pd

        def write_icr_outputs(df_icr, folder):
            df_icr.to_csv(folder / "icr_goldstandard.csv")
            return folder

        def load_icr_progress(path):
            return pd.read_csv(path)
    """)
    by_name = _index(scan_path(tmp_path))
    assert "statistical" not in by_name["write_icr_outputs"].hazard_kinds
    assert "statistical" not in by_name["load_icr_progress"].hazard_kinds
    assert by_name["write_icr_outputs"].suggested == "data_output"


def test_a_name_hint_alone_does_not_make_a_statistic(tmp_path):
    """It must actually compute: a menu prompt that says "icr" is not a statistic."""
    _write(tmp_path, "menu.py", """
        def _ask_fix_icr():
            v = input("FIX-ICR pass? [y/N]: ").strip().lower()
            return "fix-icr" if v in ("y", "yes") else ""

        def mean_agreement(scores):
            return sum(scores) / len(scores)
    """)
    by_name = _index(scan_path(tmp_path))
    assert "statistical" not in by_name["_ask_fix_icr"].hazard_kinds
    assert "human_decision" in by_name["_ask_fix_icr"].hazard_kinds
    assert "statistical" in by_name["mean_agreement"].hazard_kinds   # it computes


def test_unit_of_analysis_marks_where_the_sample_shrinks(tmp_path):
    _write(tmp_path, "filter.py", """
        def filter_positives(df):
            return df.dropna(subset=["label"]).drop_duplicates()
    """)
    rec = _index(scan_path(tmp_path))["filter_positives"]
    assert "unit_of_analysis" in rec.hazard_kinds


def test_a_validation_nobody_calls_is_worse_than_no_validation(tmp_path):
    """The AST can prove the guard is never invoked -- it only looks like safety."""
    _write(tmp_path, "guards.py", """
        def check_schema_integrity(df):
            assert "id" in df.columns
            return True

        def validate_rows(df):
            assert len(df) > 0
            return True

        def main(df):
            validate_rows(df)
            return df
    """)
    by_name = _index(scan_path(tmp_path))
    called = by_name["validate_rows"].hazard("validation")
    orphan = by_name["check_schema_integrity"].hazard("validation")
    assert "never called" not in called.reason
    assert "never called" in orphan.reason


def test_hazards_propagate_to_callers_as_indirect(tmp_path):
    """``classify_paper`` never touches the client -- its callee does."""
    _write(tmp_path, "chain.py", """
        from openai import OpenAI

        def _call(client, msgs):
            return client.chat.completions.create(messages=msgs)

        def classify_paper(client, text):
            return _call(client, [text])

        def main(client, papers):
            return [classify_paper(client, p) for p in papers]
    """)
    by_name = _index(scan_path(tmp_path))
    assert by_name["_call"].hazard("model_call").indirect is False
    for name in ("classify_paper", "main"):
        haz = by_name[name].hazard("model_call")
        assert haz is not None and haz.indirect is True


def test_annotated_functions_are_still_screened_for_hazards(tmp_path):
    """The two axes are orthogonal: carrying @mapping does not exempt you."""
    _write(tmp_path, "annotated.py", """
        import krippendorff
        from rse_annotations import mapping

        @mapping
        def compute_dimension_icr(a, b):
            return krippendorff.alpha(reliability_data=[a, b])
    """)
    rec = _index(scan_path(tmp_path))["compute_dimension_icr"]
    assert rec.annotated and rec.kind == "mapping"
    assert "statistical" in rec.hazard_kinds


def test_hazards_reach_the_report_and_both_renderers(tmp_path):
    _write(tmp_path, "haz.py", """
        import random
        from openai import OpenAI

        def ask(client, text):
            return client.chat.completions.create(messages=[text])

        def pick(xs, seed):
            return random.Random(seed).choice(xs)

        def plain(x):
            return x + 1
    """)
    report = scan_path(tmp_path)
    assert report.counts_by_hazard()["model_call"] == 1
    assert {r.name for r in report.hazardous} == {"ask", "pick"}
    assert report.hazard_rate == pytest.approx(2 / 3)

    text = render_coverage_text(report)
    assert "Audit hazards" in text and "@model_call" in text

    md = render_coverage_markdown(report)
    assert "## Audit hazards" in md and "`@stochastic`" in md


def test_a_clean_codebase_reports_no_hazards(tmp_path):
    """The hazard tables must not appear when there is nothing to report."""
    _write(tmp_path, "clean.py", """
        def normalise(x, y):
            return (x - y) / (x + y)
    """)
    report = scan_path(tmp_path)
    assert report.hazardous == [] and report.hazard_rate == 0.0
    assert "Audit hazards" not in render_coverage_text(report)
