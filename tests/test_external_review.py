"""The external review: an outside reviewer steps through the marked snippets."""

from rse_annotations import ExternalReviewer, ProtocolStore, TargetProject
from rse_annotations.cli import main
from rse_annotations.inspection import PROTOCOL_FILE, load_protocol
from rse_annotations.inspection.external import question, review_items

# Does not import (no such module) -- the review must not care.
SAMPLE = '''\
import a_gpu_library_that_is_not_installed as gpu

from rse_annotations import data_input, functional, hardware_dependency


@hardware_dependency(fields={"device": "one GPU with 8 GB of memory"})
def train():
    with gpu.device("/GPU:0"):
        return gpu.fit()


@functional
def ratio(a, b):
    return a / b


def glue():
    print("not marked")
'''


def _target(tmp_path):
    (tmp_path / "model.py").write_text(SAMPLE, encoding="utf-8")
    return TargetProject(tmp_path)


def _review(target, answers, msgs=None):
    feed = iter(answers)

    def answer(_prompt):
        try:
            return next(feed)
        except StopIteration:  # the reviewer closed the session (Ctrl-D)
            raise EOFError from None

    reviewer = ExternalReviewer(ProtocolStore.for_target(target), input_fn=answer,
                                output_fn=(msgs.append if msgs is not None else lambda _m: None))
    return reviewer.review(target)


def test_items_cover_every_concern_in_listing_order(tmp_path):
    _, items = review_items(_target(tmp_path))
    assert [(str(i.record.concern), i.record.name) for i in items] == [
        ("functional", "ratio"), ("hardware_dependency", "train")]
    train = items[1]
    assert train.location == "model.py:7"
    assert train.notes == {"device": "one GPU with 8 GB of memory"}
    assert train.source.startswith("@hardware_dependency(") and "gpu.fit()" in train.source


def test_reviewer_is_asked_the_question_of_each_concern(tmp_path):
    msgs = []
    _review(_target(tmp_path), ["JOSS editor", "y", "", "n", "README names no GPU"], msgs)
    text = "\n".join(msgs)
    assert f"== @hardware_dependency -- {question('hardware_dependency')}" in text
    assert "[2/2] train   (model.py:7)" in text
    assert "authors' note, device: one GPU with 8 GB of memory" in text
    assert "glue" not in text


def test_review_writes_a_protocol(tmp_path):
    target = _target(tmp_path)
    protocol = _review(target, ["JOSS editor", "y", "", "n", "README names no GPU"])
    assert [(f.function, f.verdict, f.note) for f in protocol.findings] == [
        ("ratio", "accepted", ""), ("train", "declined", "README names no GPU")]

    saved = load_protocol(tmp_path / PROTOCOL_FILE)
    assert saved == protocol
    assert saved.reviewer == "JOSS editor"
    assert saved.scope.startswith("2 of 3 eligible function(s) marked")
    assert saved.findings[1].question == question("hardware_dependency")
    # the authors' own log is a different file and is left alone
    assert not (tmp_path / "inspection.yaml").exists()


def test_rerun_prefills_the_previous_answers(tmp_path):
    target = _target(tmp_path)
    _review(target, ["JOSS editor", "y", "", "n", "README names no GPU"])
    msgs = []
    protocol = _review(target, ["", "", "", "y", "fixed in v1.1"], msgs)  # Enter keeps
    assert protocol.reviewer == "JOSS editor"
    assert [(f.verdict, f.note) for f in protocol.findings] == [
        ("accepted", ""), ("accepted", "fixed in v1.1")]
    assert "(previously: declined -- README names no GPU)" in "\n".join(msgs)


def test_review_shows_the_authors_verdict(tmp_path):
    from rse_annotations.inspection import Verdict, VerdictStore

    target = _target(tmp_path)
    VerdictStore.for_target(target).save([Verdict(
        function="ratio", location=f"{tmp_path / 'model.py'}:13", concern="functional",
        formula="a / b", verdict="accepted")])
    _, items = review_items(target)
    assert [i.author_verdict for i in items] == ["accepted", None]
    msgs = []
    _review(target, [], msgs)  # no answers at all: everything stays pending
    assert "authors' own verdict: accepted" in "\n".join(msgs)


def test_cli_review_runs_without_importing(tmp_path):
    _target(tmp_path)
    msgs = []
    answers = iter(["reviewer 2", "y", "", "s", ""])
    rc = main([str(tmp_path), "--review"], input_fn=lambda _p: next(answers),
              output_fn=msgs.append)
    assert rc == 0
    saved = load_protocol(tmp_path / PROTOCOL_FILE)
    assert [f.verdict for f in saved.findings] == ["accepted", "pending"]
    assert not any("could not import" in str(m) for m in msgs)


def test_cli_menu_offers_the_review_as_fourth_mode(tmp_path):
    _target(tmp_path)
    answers = iter(["4", "reviewer 2", "n", "denominator can be zero", "y", ""])
    rc = main([str(tmp_path)], input_fn=lambda _p: next(answers), output_fn=lambda _m: None)
    assert rc == 0
    saved = load_protocol(tmp_path / PROTOCOL_FILE)
    assert saved.findings[0].note == "denominator can be zero"
