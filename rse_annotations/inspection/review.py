"""Human review of ``@functional`` code: the :class:`Reviewer` loop.

The machine proposes (source + inferred formula), the human decides (accept /
decline / skip). Verdicts persist in ``inspection.yaml`` next to the code, so the
review is auditable and a re-run pre-fills the previous answers. Machine evidence
never goes into that file -- it holds human judgement only.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from .formula import infer_formula
from .verdicts import VERDICTS, Verdict, VerdictStore
from ..decorators.registry import DecoratorInfo
from .snippets import extract_snippet
from ..decorators.markers import HazardDecorator


class Reviewer:
    """Steps a human through every ``@functional`` and records a verdict for each.

    Args:
        store: Where verdicts are read from and written to.
        input_fn / output_fn: Injectable I/O (tests pass lists; the CLI passes
            ``input`` / ``print``).
    """

    prompt = "Accept this @functional as correct? [y]es / [n]o / [s]kip > "

    def __init__(self, store: VerdictStore, *,
                 input_fn: Callable[[str], str] = input,
                 output_fn: Callable[[str], None] = print) -> None:
        self.store = store
        self.input_fn = input_fn
        self.output_fn = output_fn

    def review(self, infos: List[DecoratorInfo]) -> List[Verdict]:
        """Review the ``@functional`` entries of ``infos``; write and return the verdicts."""
        out = self.output_fn
        functional = [i for i in infos if i.concern == HazardDecorator.FUNCTIONAL]
        previous = self.store.by_function()

        if not functional:
            out("No @functional decorators found to inspect.")
            self.store.save([])
            return []

        verdicts: List[Verdict] = []
        for idx, info in enumerate(functional, start=1):
            prior = previous.get((info.name, info.location))
            formula = self.formula_line(info)
            self.present(info, formula, prior, idx, len(functional))
            verdicts.append(Verdict(
                function=info.name, location=info.location, concern=info.concern,
                formula=formula, verdict=self.ask(prior.verdict if prior else "pending")))

        self.store.save(verdicts)
        counts = {k: sum(1 for v in verdicts if v.verdict == k) for k in VERDICTS}
        out("")
        out(f"Recorded {len(verdicts)} verdict(s): {counts['accepted']} accepted, "
            f"{counts['declined']} declined, {counts['pending']} pending.")
        out(f"Written to {self.store.path}")
        return verdicts

    # ---- steps a subclass may override --------------------------------- #
    @staticmethod
    def formula_line(info: DecoratorInfo) -> str:
        res = infer_formula(info)
        if res.ast_forms:
            return res.ast_forms[0]
        if res.sympy_form:
            return res.sympy_form
        return "(no closed-form formula could be inferred; inspect the source)"

    def present(self, info: DecoratorInfo, formula: str, prior: Optional[Verdict],
                idx: int, total: int) -> None:
        out = self.output_fn
        out("")
        out(f"[{idx}/{total}] {info.name}   ({info.location})")
        out(f"formula: {formula}")
        if prior and prior.verdict in VERDICTS:
            out(f"(previously: {prior.verdict})")
        out("--- source ---")
        for src_line in extract_snippet(info).source.splitlines():
            out(f"    {src_line}")

    def ask(self, default: str) -> str:
        """One accept/decline/skip answer; EOF or empty input keeps ``default``."""
        while True:
            try:
                answer = self.input_fn(self.prompt).strip().lower()
            except EOFError:
                return default
            if answer == "":
                return default
            if answer in ("y", "yes"):
                return "accepted"
            if answer in ("n", "no"):
                return "declined"
            if answer in ("s", "skip"):
                return "pending"
            self.output_fn("  please answer y, n, or s")
