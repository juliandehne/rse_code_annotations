"""Human inspection machinery: show code and its inferred maths, record verdicts.

* :mod:`.review` -- :class:`Reviewer` (the interactive loop), :class:`VerdictStore`
  (``inspection.yaml``);
* :mod:`.formula` -- infer the formula behind a ``@functional``;
* :mod:`.snippets` -- extract the source a human looks at;
* :mod:`.checks` -- per-annotation convention and I/O checks.
"""

from .checks import CheckResult, all_checks, check_docstring, check_io_success, check_placement
from .formula import FormulaResult, infer_formula, render_formula
from .review import VERDICT_FILE, Reviewer, VerdictStore
from .snippets import Snippet, extract_snippet
from .verdicts import VERDICTS, Verdict, dump_yaml, load_yaml, run_inspection

__all__ = ["Reviewer", "VerdictStore", "VERDICT_FILE", "Verdict", "VERDICTS",
           "dump_yaml", "load_yaml", "run_inspection", "FormulaResult", "infer_formula",
           "render_formula", "Snippet", "extract_snippet", "CheckResult", "all_checks",
           "check_placement", "check_docstring", "check_io_success"]
