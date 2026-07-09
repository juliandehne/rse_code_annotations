"""Tests for the framework itself (no network / no LLM required)."""

from __future__ import annotations

import os
import sys
import textwrap

import pytest

# Make the project root importable when run from anywhere.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rse_annotations import (  # noqa: E402
    REGISTRY,
    Runner,
    annotation_of,
    data_input,
    data_output,
    functional,
    mapping,
)
from rse_annotations import checks  # noqa: E402
from rse_annotations.snippets import extract_snippet  # noqa: E402


def test_decorator_preserves_behaviour_and_metadata():
    @functional
    def add(a, b):
        "Add two numbers. :param a: :param b: :returns: a+b."
        return a + b

    assert add(2, 3) == 5
    info = annotation_of(add)
    assert info is not None
    assert info.kind == "functional"
    assert info.name == "add"


def test_functional_purity_placement_fails_on_io():
    @functional
    def bad(path):
        "reads a file"
        with open(path) as fh:
            return fh.read()

    result = checks.check_placement(annotation_of(bad))
    assert result.status == "fail"


def test_data_input_placement_passes_with_read():
    @data_input
    def rd(path):
        "read something. :param path:"
        with open(path) as fh:
            return fh.read()

    assert checks.check_placement(annotation_of(rd)).status == "pass"


def test_docstring_check_requires_fields():
    @mapping(fields={"x": "the input", "y": "the output"})
    def transform(x):
        "Only documents x here."  # missing 'y'
        return x

    res = checks.check_docstring(annotation_of(transform))
    assert res.status == "fail"
    assert "y" in res.message


def test_io_success_check_observes_write(tmp_path):
    @data_input
    def rd(p):
        "read. :param p:"
        with open(p) as fh:
            return fh.read()

    def fixture(tmpdir, tracer):
        path = os.path.join(tmpdir, "f.txt")
        with open(path, "w") as fh:
            fh.write("hello")
        tracer.reads.clear()
        tracer.writes.clear()
        return (path,), {}

    res = checks.check_io_success(annotation_of(rd), fixture=fixture)
    assert res.status == "pass", res.message


def test_extract_snippet_contains_source():
    @functional
    def sq(x):
        "square. :param x: :returns: x*x."
        return x * x

    snip = extract_snippet(annotation_of(sq))
    assert "return x * x" in snip.source
    assert snip.name == "sq"


def test_runner_end_to_end_on_example():
    from examples import fixtures as fx

    runner = Runner("examples.sample_pipeline", fixtures=fx.FIXTURES)
    report = runner.run()

    by_name = {fr.name: fr for fr in report.functions}
    # good functional passes placement
    assert by_name["normalize"].status == "pass"
    # mis-annotated functional fails
    assert by_name["impure_sum"].status == "fail"
    # undocumented mapping fails docstring
    assert by_name["untidy"].status == "fail"
    # snippets emitted for every @functional
    functional_names = {s.name for s in report.snippets}
    assert {"normalize", "mean", "impure_sum"} <= functional_names


def test_formula_inference_ast_and_sympy():
    from rse_annotations.formula import infer_formula

    @functional
    def rescale(x, lo, hi):
        "affine rescale"
        return lo + x * (hi - lo)

    res = infer_formula(annotation_of(rescale))
    assert res.ast_forms, "AST backend should always render a return expression"
    assert "lo" in res.ast_forms[0] and "hi" in res.ast_forms[0]
    # sympy is a dev dependency; if present it should simplify to a closed form.
    try:
        import sympy  # noqa: F401
        assert res.sympy_form is not None
    except ImportError:
        pass


def test_formula_inference_handles_non_arithmetic_gracefully():
    from rse_annotations.formula import infer_formula

    @functional
    def pick(items):
        "not scalar arithmetic"
        return [x for x in items if x]

    res = infer_formula(annotation_of(pick))
    # Must not raise; sympy simply reports it does not apply.
    assert isinstance(res.notes, list)


def test_differential_check_passes_on_equivalent_impls():
    from rse_annotations.verify import differential_check

    def candidate(a, b):
        return a * a - b * b

    def reference(a, b):
        return (a - b) * (a + b)

    def gen(rng):
        return (rng.uniform(-10, 10), rng.uniform(-10, 10))

    res = differential_check(candidate, reference, gen, trials=100)
    assert res.ok, res.failures
    assert res.checked == 100
    assert res.worst_delta < 1e-9


def test_differential_check_detects_mismatch():
    from rse_annotations.verify import differential_check

    def candidate(a, b):
        return a + b + 1  # deliberately wrong

    def reference(a, b):
        return a + b

    def gen(rng):
        return (rng.randint(0, 5), rng.randint(0, 5))

    res = differential_check(candidate, reference, gen, trials=50)
    assert not res.ok
    assert res.failures


def test_differential_check_skips_when_reference_rejects():
    from rse_annotations.verify import differential_check

    def candidate(x):
        return 1.0 / x

    def reference(x):
        if x == 0:
            raise ZeroDivisionError  # out of domain -> skipped, not a failure
        return 1.0 / x

    def gen(rng):
        return (rng.randint(0, 3),)  # sometimes 0

    res = differential_check(candidate, reference, gen, trials=60)
    assert res.skipped > 0
    assert res.ok  # every comparable trial agrees


def test_runner_accepts_multiple_targets():
    from examples import fixtures as fx

    report = Runner(["examples.sample_pipeline"], fixtures=fx.FIXTURES).run()
    assert {fr.name for fr in report.functions}  # non-empty


# --------------------------------------------------------------------------- #
# Path-based discovery
# --------------------------------------------------------------------------- #

_SAMPLE_MODULE = '''
from rse_annotations import functional, mapping, data_input, data_output


@functional
def area(w, h):
    "rectangle area. :param w: :param h: :returns:"
    return w * h


@mapping(fields={"raw": "raw rows", "clean": "cleaned rows"})
def tidy(raw):
    "tidy raw into clean. :param raw: :returns clean:"
    return [r for r in raw if r]


@data_input(fields={"path": "file to read", "rows": "records"})
def load(path):
    "read rows. :param path: :returns rows:"
    with open(path) as fh:
        return fh.read()


@data_output(fields={"rows": "records to write", "path": "target file"})
def store(rows, path):
    "write rows. :param rows: :param path:"
    with open(path, "w") as fh:
        fh.write(str(rows))
'''


def _write_sample(tmp_path, stem):
    src = tmp_path / f"{stem}.py"
    src.write_text(textwrap.dedent(_SAMPLE_MODULE), encoding="utf-8")
    return src


def test_discover_path_finds_all_kinds(tmp_path):
    from rse_annotations.discovery import discover_path

    _write_sample(tmp_path, "pkg_discover")
    infos = discover_path(tmp_path)
    by_kind = {i.kind for i in infos}
    assert {"functional", "mapping", "data_input", "data_output"} <= by_kind
    names = {i.name for i in infos}
    assert {"area", "tidy", "load", "store"} <= names


# --------------------------------------------------------------------------- #
# Pattern-based stub generation
# --------------------------------------------------------------------------- #

def test_generate_stub_files_covers_every_kind(tmp_path):
    from rse_annotations.discovery import discover_path
    from rse_annotations.stubs import generate_stub_files

    _write_sample(tmp_path, "pkg_stub")
    infos = discover_path(tmp_path)
    files = generate_stub_files(infos, tmp_path / "test_stubs")
    assert files
    blob = "\n".join(sf.content for sf in files)
    # one test per annotation, each a skipped scaffold
    assert "def test_area_is_deterministic" in blob
    assert "def test_tidy_transforms_shape" in blob
    assert "def test_load_reads_source(tmp_path)" in blob
    assert "def test_store_writes_sink(tmp_path)" in blob
    assert "pytest.skip" in blob
    assert "import pytest" in blob


# --------------------------------------------------------------------------- #
# Interactive inspection
# --------------------------------------------------------------------------- #

def test_run_inspection_records_and_roundtrips(tmp_path):
    from rse_annotations.discovery import discover_path
    from rse_annotations.inspection import load_yaml, run_inspection

    _write_sample(tmp_path, "pkg_inspect")
    infos = discover_path(tmp_path)
    answers = iter(["y"])  # single @functional (area) -> accept

    out = tmp_path / "inspection.yaml"
    verdicts = run_inspection(
        infos, out,
        input_fn=lambda _prompt: next(answers),
        output_fn=lambda _msg: None,
    )
    assert [v.verdict for v in verdicts] == ["accepted"]
    assert out.exists()
    reloaded = load_yaml(out)
    assert reloaded[0].function == "area"
    assert reloaded[0].verdict == "accepted"


def test_run_inspection_default_on_empty_answer(tmp_path):
    from rse_annotations.discovery import discover_path
    from rse_annotations.inspection import run_inspection

    _write_sample(tmp_path, "pkg_inspect_default")
    infos = discover_path(tmp_path)
    out = tmp_path / "inspection.yaml"
    verdicts = run_inspection(
        infos, out,
        input_fn=lambda _prompt: "",       # accept the default -> pending
        output_fn=lambda _msg: None,
    )
    assert verdicts[0].verdict == "pending"


# --------------------------------------------------------------------------- #
# CLI: the two-option tool
# --------------------------------------------------------------------------- #

def test_cli_stubs_mode_writes_files(tmp_path):
    from rse_annotations.cli import main

    _write_sample(tmp_path, "pkg_cli_stub")
    msgs = []
    rc = main([str(tmp_path), "--stubs"], output_fn=msgs.append)
    assert rc == 0
    stub_dir = tmp_path / "test_stubs"
    assert stub_dir.is_dir()
    assert list(stub_dir.glob("test_*.py"))


def test_cli_inspect_mode_writes_yaml(tmp_path):
    from rse_annotations.cli import main

    _write_sample(tmp_path, "pkg_cli_inspect")
    answers = iter(["n"])
    rc = main(
        [str(tmp_path), "--inspect"],
        input_fn=lambda _p: next(answers),
        output_fn=lambda _m: None,
    )
    assert rc == 0
    assert (tmp_path / "inspection.yaml").exists()


def test_cli_menu_dispatches_on_choice(tmp_path):
    from rse_annotations.cli import main

    _write_sample(tmp_path, "pkg_cli_menu")
    # first prompt is the menu ("2" -> stubs); no further input needed
    answers = iter(["2"])
    rc = main(
        [str(tmp_path)],
        input_fn=lambda _p: next(answers),
        output_fn=lambda _m: None,
    )
    assert rc == 0
    assert (tmp_path / "test_stubs").is_dir()


def test_cli_reports_empty_directory(tmp_path):
    from rse_annotations.cli import main

    msgs = []
    rc = main([str(tmp_path)], output_fn=msgs.append)
    assert rc == 0
    assert any("0 annotation" in m for m in msgs)
