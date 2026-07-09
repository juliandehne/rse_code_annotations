"""Tests for the framework itself (no network / no Fable required)."""

from __future__ import annotations

import os
import sys

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
    functional,
    mapping,
)
from rse_annotations import checks  # noqa: E402
from rse_annotations.fable import extract_snippet, fable_available  # noqa: E402


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

    runner = Runner(
        "examples.sample_pipeline",
        fixtures=fx.FIXTURES,
        generate_stubs=False,  # never touch the network in tests
    )
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
    # stubs disabled -> fable reported unavailable/disabled
    assert report.fable is not None and not report.fable.available


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

    report = Runner(
        ["examples.sample_pipeline"],  # list form
        fixtures=fx.FIXTURES,
        generate_stubs=False,
    ).run()
    assert {fr.name for fr in report.functions}  # non-empty


def test_fable_available_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    status = fable_available(probe=False)
    # Either SDK missing or key missing -> unavailable, with a reason.
    assert not status.available
    assert status.reason
