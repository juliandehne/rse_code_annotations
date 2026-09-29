"""Test generation and differential verification behind classes.

* :class:`TestGenerator` -- pattern-based ``pytest`` scaffolds for every annotation
  of a target (no LLM). Override :meth:`TestGenerator.stub_files` to change how
  stubs are made.
* :class:`DifferentialVerifier` -- run a ``@functional`` against a trusted reference
  on seeded random inputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, List, Optional

from .stubs import StubFile, generate_stub_files
from .verify import DiffResult, differential_check


class TestGenerator:
    """Writes ``tests/test_<module>.py`` scaffolds for a target project."""

    __test__ = False  # not a pytest test class, despite the name

    def __init__(self, target, out_dir=None) -> None:
        self.target = target
        self.out_dir = Path(out_dir) if out_dir is not None else target.output_path("tests")

    def stub_files(self) -> List[StubFile]:
        """The files that would be written; nothing touches the disk."""
        return generate_stub_files(self.target.annotations(), self.out_dir)

    def write(self, output_fn: Callable[[str], None] = print) -> List[StubFile]:
        """Write the scaffolds and report each file through ``output_fn``."""
        files = self.stub_files()
        if not files:
            output_fn("No annotations found; nothing to scaffold.")
            return files
        self.out_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        for sf in files:
            sf.path.write_text(sf.content, encoding="utf-8")
            output_fn(f"  wrote {sf.path}  ({sf.stub_count} annotation(s) from {sf.source_module})")
            written += sf.stub_count
        output_fn("")
        output_fn(f"Generated {written} stub(s) across {len(files)} file(s) in {self.out_dir}")
        output_fn("Every test is a SKIPPED scaffold -- fill in the TODOs to make them run.")
        return files


class DifferentialVerifier:
    """Compares a candidate against a reference implementation on random inputs.

    Settings are fixed at construction so one verifier can check many pairs the same
    way; see :func:`~rse_annotations.verify.differential_check` for their meaning.
    """

    def __init__(self, *, trials: int = 200, seed: int = 12345, tol: float = 1e-9,
                 compare: Optional[Callable] = None, skip_value: Any = None) -> None:
        self.trials, self.seed, self.tol = trials, seed, tol
        self.compare, self.skip_value = compare, skip_value

    def check(self, candidate: Callable, reference: Callable, gen_inputs: Callable) -> DiffResult:
        return differential_check(candidate, reference, gen_inputs, trials=self.trials,
                                  seed=self.seed, tol=self.tol, compare=self.compare,
                                  skip_value=self.skip_value)
