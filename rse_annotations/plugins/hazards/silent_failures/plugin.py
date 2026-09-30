"""Hazard plugin ``silent_failures`` -- a stub for students to implement.

Responsible RSE, question 2: *is the work fair to the evidence and honest about it?*

See :mod:`rse_annotations.plugins.hazards._stub` for how to turn the stub into a
working plugin.
"""

from __future__ import annotations

from .._stub import HazardStub


class SilentFailure(HazardStub):
    """TODO (Tier A, S): code that silently changes the sample or the numbers.

    Inside annotated functions only, detect ``except: pass`` / ``except Exception:
    continue`` without logging or a counter; ``pd.to_numeric(errors="coerce")``;
    ``read_csv(on_bad_lines="skip")``; ``warnings.filterwarnings("ignore")``;
    ``np.seterr(all="ignore")``; ``dropna()`` / ``drop_duplicates()`` whose row delta is
    not recorded. Severity: ``fail`` in unit-of-analysis / statistical code, ``warn`` in
    ``@data_input``. Suggest a sample-accounting counter as the fix.
    Tools: ruff S110 / BLE001 / E722 plus own AST visitors (reuse ``coverage.py``'s walker).
    Implement: ``analyze(target)`` over ``target.static_scan()``.
    Difficulty: 2/5 (~2 h/week) -- pure AST pattern matching on a fixed list, reusing the
      existing walker; most time goes into test fixtures.
    EVERSE: dimension ``reliability``; indicators ``has_no_linting_issues`` /
      ``uses_tool_for_warnings_and_mistakes`` (generic; this is the research-specific
      slice); RSQKit https://everse.software/RSQKit/static_analysis .
    """

    name = "silent_failures"
    description = "swallowed errors, coerced values and unrecorded row drops"
    question = "is the work fair to the evidence and honest about it?"
    tier, effort, proposal = "A", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.2"
    difficulty = 2
    hooks = ("@data_input", "@mapping", "unit_of_analysis", "statistical")
    tools = ("ruff",)
