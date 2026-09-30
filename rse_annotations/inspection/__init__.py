"""Human inspection: show code and its inferred maths, record the verdicts.

* :mod:`.review` -- :class:`Reviewer`, the interactive loop;
* :mod:`.verdicts` -- :class:`Verdict` and :class:`VerdictStore` (``inspection.yaml``);
* :mod:`.formula` -- infer the formula behind a ``@functional``;
* :mod:`.snippets` -- extract the source a human looks at.
"""

from .formula import FormulaResult, infer_formula, render_formula
from .review import Reviewer
from .snippets import Snippet, extract_snippet
from .verdicts import VERDICT_FILE, VERDICTS, Verdict, VerdictStore, dump_yaml, load_yaml

__all__ = ["Reviewer", "VerdictStore", "VERDICT_FILE", "Verdict", "VERDICTS",
           "dump_yaml", "load_yaml", "FormulaResult", "infer_formula",
           "render_formula", "Snippet", "extract_snippet"]
