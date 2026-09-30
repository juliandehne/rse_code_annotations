"""Differential verification of a ``@functional`` against a trusted reference.

Formula *inference* (see :mod:`rse_annotations.inspection.formula`) renders the maths a
function computes so a human can read it -- but it is not a proof. The honest way
to pin correctness is to keep a second, independent implementation and check the
two agree on many inputs. That second implementation might be a textbook formula,
a slow-but-obvious brute force, or a trusted third-party library.

``differential_check`` is the reusable harness for that: you supply the candidate
callable, the reference callable, and a generator that produces random argument
tuples; it runs both on each input and reports where (and by how much) they differ.

This is framework logic, deliberately kept independent of any particular domain:
the *what* to compare against lives in your project, the *how* lives here.

Example::

    import random, numpy as np
    from rse_annotations.testing.verify import differential_check

    def gen(rng: random.Random):
        n = rng.randint(4, 20)
        data = np.random.default_rng(rng.getrandbits(32)).integers(0, 3, size=(2, n))
        return (data.astype(float),)

    result = differential_check(my_alpha, library_alpha, gen, trials=200)
    assert result.ok, result.failures
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence, Tuple

# A generator takes a seeded RNG and returns the positional args for one trial.
InputGen = Callable[[random.Random], Sequence[Any]]
# A comparator returns (equal, distance) for a candidate/reference value pair.
Comparator = Callable[[Any, Any], Tuple[bool, float]]


@dataclass
class DiffResult:
    """Outcome of a :func:`differential_check` run."""

    checked: int = 0
    skipped: int = 0
    worst_delta: float = 0.0
    failures: List[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures and self.checked > 0

    @property
    def inconclusive(self) -> bool:
        return self.checked == 0

    def summary(self) -> str:
        if self.inconclusive:
            return ("differential check INCONCLUSIVE -- no comparable trials "
                    "(reference unavailable or every input skipped)")
        state = "PASS" if self.ok else f"FAIL ({len(self.failures)} disagreement(s))"
        return (f"differential check {state} -- {self.checked} checked, "
                f"{self.skipped} skipped, worst |delta| {self.worst_delta:.3e}")


def _numeric_compare(tol: float) -> Comparator:
    def cmp(cand: Any, ref: Any) -> Tuple[bool, float]:
        delta = abs(float(cand) - float(ref))
        return delta <= tol, delta
    return cmp


def differential_check(
    candidate: Callable[..., Any],
    reference: Callable[..., Any],
    gen_inputs: InputGen,
    *,
    trials: int = 200,
    seed: int = 12345,
    tol: float = 1e-9,
    compare: Optional[Comparator] = None,
    skip_value: Any = None,
) -> DiffResult:
    """Run ``candidate`` and ``reference`` on random inputs and compare results.

    Args:
        candidate: the function under test (typically a ``@functional``).
        reference: the trusted implementation to compare against. If it raises
            or returns ``skip_value`` for an input, that trial is skipped (the
            input is treated as out of the reference's domain).
        gen_inputs: ``gen(rng) -> args`` producing the positional args for one
            trial. Receives a seeded :class:`random.Random` so runs are
            reproducible; call it as ``candidate(*args)`` / ``reference(*args)``.
        trials: number of random inputs to try.
        seed: RNG seed for reproducibility.
        tol: absolute tolerance for the default numeric comparator.
        compare: optional ``cmp(cand, ref) -> (equal, distance)`` overriding the
            default numeric comparison (use for non-scalar outputs).
        skip_value: a reference return value that means "skip this trial"
            (default ``None``).

    Returns:
        A :class:`DiffResult` with pass/skip counts, the worst distance seen, and
        up to a handful of recorded failures.
    """
    cmp = compare or _numeric_compare(tol)
    rng = random.Random(seed)
    result = DiffResult()

    for t in range(trials):
        args = gen_inputs(rng)
        try:
            ref = reference(*args)
        except Exception:  # noqa: BLE001 - reference rejects -> out of domain
            result.skipped += 1
            continue
        if ref is skip_value:
            result.skipped += 1
            continue

        cand = candidate(*args)
        equal, delta = cmp(cand, ref)
        result.worst_delta = max(result.worst_delta, delta)
        result.checked += 1
        if not equal:
            if len(result.failures) < 10:
                result.failures.append(
                    {"trial": t, "candidate": cand, "reference": ref, "delta": delta})

    return result
