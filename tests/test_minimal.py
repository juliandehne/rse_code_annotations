import json
import textwrap

from rse_annotations import CONCERNS, functional, mapping
from rse_annotations.__main__ import main
from rse_annotations.analysis import scan
from rse_annotations.inspection import formula, review
from rse_annotations.inspection.verdicts import Verdict, dump, load

CODE = textwrap.dedent('''
    import random
    from rse_annotations import functional, model_call

    @functional
    def scale(x, k):
        return x * k

    @functional
    def leaky(path):
        return open(path).read()

    def ask(client):
        return client.chat.completions.create(model="m")

    def run(n):
        random.shuffle([1, 2])
        return ask(None)
''')


def _write(tmp_path):
    (tmp_path / "pipe.py").write_text(CODE, encoding="utf-8")
    return tmp_path


def test_decorators_mark_and_return_the_function():
    @functional
    def f(x):
        return x

    @mapping(fields={"x": "in"})
    def g(x):
        return x

    assert f(2) == 2 and g(3) == 3
    assert f.__rse_concerns__ == (("functional", {}),)
    assert g.__rse_concerns__ == (("mapping", {"fields": {"x": "in"}}),)


def test_every_concern_is_a_folder_with_help_and_detector():
    assert {"functional", "data_input", "model_call", "stochastic"} <= set(CONCERNS)
    for c in CONCERNS.values():
        assert c.help and callable(c.detect)


def test_scan_marks_detection_and_propagation(tmp_path):
    recs = {r.qualname: r for r in scan(_write(tmp_path))[0]}
    assert recs["scale"].marked == ["functional"] and "functional" in recs["scale"].detected
    assert "functional" not in recs["leaky"].detected          # marked but not detected
    assert recs["ask"].detected["model_call"].confidence == "high"
    run = recs["run"].detected
    assert run["model_call"].indirect and "no seed" in run["stochastic"].reason


def test_runner_text_and_json(tmp_path, capsys):
    _write(tmp_path)
    main([str(tmp_path)])
    out = capsys.readouterr().out
    assert "Marked but not detected" in out and "leaky" in out
    main([str(tmp_path), "--json"])
    assert len(json.loads(capsys.readouterr().out)["functions"]) == 4


def test_formula():
    assert formula("def f(a, b):\n    '''doc'''\n    return a + b\n") == "f(...) = a + b"
    assert formula("def f(a):\n    x = a\n    return x\n") == ""


def test_review_saves_and_prefills(tmp_path):
    root = _write(tmp_path)
    answers = iter(["y", "n"])
    review(root, input_fn=lambda _: next(answers), output_fn=lambda _: None)
    saved = {v.function: v.verdict for v in load(root / "inspection.yaml")}
    assert saved == {"scale": "accepted", "leaky": "declined"}
    again = review(root, input_fn=lambda _: "", output_fn=lambda _: None)  # defaults kept
    assert [v.verdict for v in again] == ["accepted", "declined"]


def test_yaml_round_trip(tmp_path):
    v = Verdict("f", 'a "b"\\c.py:1', "functional", "f(...) = x", "accepted", "ok")
    (tmp_path / "i.yaml").write_text(dump([v]), encoding="utf-8")
    assert load(tmp_path / "i.yaml") == [v]
