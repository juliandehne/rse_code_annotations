"""Human inspection: show code and its inferred maths, record the verdicts.

* :mod:`.review` -- :class:`Reviewer`, the authors' interactive loop;
* :mod:`.external` -- :class:`ExternalReviewer`, the interactive loop of an outside
  reviewer, and :class:`ProtocolStore` (``review_protocol.yaml``);
* :mod:`.verdicts` -- :class:`Verdict` and :class:`VerdictStore` (``inspection.yaml``);
* :mod:`.formula` -- infer the formula behind a ``@functional``;
* :mod:`.snippets` -- extract the source a human looks at.
"""

from .formula import FormulaResult, infer_formula, render_formula
from .external import (PROTOCOL_FILE, ExternalReviewer, Protocol, ProtocolStore,
                       ReviewFinding, ReviewItem, dump_protocol, load_protocol)
from .review import Reviewer
from .snippets import Snippet, extract_snippet
from .verdicts import (VERDICT_FILE, VERDICTS, Decision, Verdict, VerdictStore, count_verdicts,
                       dump_yaml, load_yaml, verdict_summary)

__all__ = ["Decision", "count_verdicts", "verdict_summary", "Reviewer", "ExternalReviewer", "ReviewItem", "Protocol", "ReviewFinding",
           "ProtocolStore", "PROTOCOL_FILE", "dump_protocol", "load_protocol", "VerdictStore", "VERDICT_FILE", "Verdict", "VERDICTS",
           "dump_yaml", "load_yaml", "FormulaResult", "infer_formula",
           "render_formula", "Snippet", "extract_snippet"]
