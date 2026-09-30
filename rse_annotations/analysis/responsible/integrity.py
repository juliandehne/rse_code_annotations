"""Responsible RSE, question 2: *is the work fair to the evidence and honest about it?*"""

from __future__ import annotations

from ._stub import ResponsibleRSEStub


class SilentFailureAnalyzer(ResponsibleRSEStub):
    """TODO (Tier A, S): code that silently changes the sample or the numbers.

    Inside annotated functions only, detect ``except: pass`` / ``except Exception:
    continue`` without logging or a counter; ``pd.to_numeric(errors="coerce")``;
    ``read_csv(on_bad_lines="skip")``; ``warnings.filterwarnings("ignore")``;
    ``np.seterr(all="ignore")``; ``dropna()`` / ``drop_duplicates()`` whose row delta is
    not recorded. Severity: ``fail`` in unit-of-analysis / statistical code, ``warn`` in
    ``@data_input``. Suggest a sample-accounting counter as the fix.
    Tools: ruff S110 / BLE001 / E722 plus own AST visitors (reuse ``coverage.py``'s walker).
    Suggested base: ``StaticAnalyzer``.
    Difficulty: 2/5 (~2 h/week) -- pure AST pattern matching on a fixed list, reusing the
      existing walker; most time goes into test fixtures.
    EVERSE: dimension ``reliability``; indicators ``has_no_linting_issues`` /
      ``uses_tool_for_warnings_and_mistakes`` (generic; this is the research-specific
      slice); RSQKit https://everse.software/RSQKit/static_analysis .
    """

    name = "silent_failures"
    description = "swallowed errors, coerced values and unrecorded row drops"
    tier, effort, proposal = "A", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.2"
    difficulty = 2
    hooks = ("@data_input", "@mapping", "unit_of_analysis", "statistical")
    tools = ("ruff",)


class UnjustifiedConstantAnalyzer(ResponsibleRSEStub):
    """TODO (Tier A, S): researcher degrees of freedom hidden in magic numbers.

    Detect numeric literals in comparisons, slicing, ``quantile``, ``head(n)``,
    ``sample(frac=)`` and filter masks inside unit-of-analysis, statistical and
    ``@mapping`` code that are not a configurable parameter and carry no justification
    (inline comment / ``rationale=``). Whitelist 0, 1, -1, 2 and array axes. List each
    constant as a candidate configuration value.
    Tools: ruff PLR2004 as a baseline, own AST for the other positions.
    Suggested base: ``StaticAnalyzer``.
    Difficulty: 2/5 (~2 h/week) -- AST plus comment lookup via ``tokenize``; the hard part
      is a whitelist that keeps false positives low.
    EVERSE: no matching indicator; closest ``functional_correctness``
      (functional_suitability) and RSQKit
      https://everse.software/RSQKit/writing_readable_code .
    """

    name = "constants"
    description = "unjustified thresholds and cut-offs in decision logic"
    tier, effort, proposal = "A", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.3"
    difficulty = 2
    hooks = ("@mapping", "unit_of_analysis", "statistical")
    tools = ("ruff",)


class LLMDisclosureAnalyzer(ResponsibleRSEStub):
    """TODO (Tier A, S): can the use of an LLM be disclosed and reproduced?

    In model-call sites detect: moving model aliases instead of dated snapshots;
    ``temperature`` / ``top_p`` / ``seed`` / ``max_tokens`` left implicit; prompts built
    from inline f-strings rather than a versioned prompt file; no open-weight baseline;
    no validation against human labels; no "LLM use" statement in README / paper.
    Output: a pre-filled disclosure paragraph (model, version, parameters, prompt hashes,
    role in the pipeline) -- no LLM involved.
    Grounding: llm-guidelines.org (Wagner et al.), TRIPOD-LLM.
    Suggested base: ``StaticAnalyzer`` (reuse the ``model_call`` hazard records).
    Difficulty: 2/5 (~2 h/week) -- static checks on existing ``model_call`` records plus a
      text template; no runtime part.
    EVERSE: no indicator for LLMs *inside* the research pipeline; RSQKit
      https://everse.software/RSQKit/ai covers gen-AI use while *developing* software
      (intensity levels 0-10) -- cite it as adjacent.
    """

    name = "llm_disclosure"
    description = "LLM usage that cannot be disclosed or reproduced as written"
    tier, effort, proposal = "A", "S", "RESPONSIBLE_RSE_PLUGINS.md §2.4"
    difficulty = 2
    hooks = ("model_call",)


class DataLeakageAnalyzer(ResponsibleRSEStub):
    """TODO (Tier B, M): train/test contamination (Yang et al., ASE 2022).

    Static: preprocessing ``fit`` / ``fit_transform`` before ``train_test_split``; test
    set evaluated repeatedly during model selection; random split on time-stamped or
    grouped data (same subject in both splits). Test mode (``when="test"`` part): hash
    the rows of the actual splits and report overlap.
    Tools: implement the preprocessing-before-split pattern in own AST first;
    ``leakage-analysis`` is heavy (Py3.8, Soufflé) -- optional backend only.
    Difficulty: 4/5 (~4 h/week) -- needs intra-procedural dataflow (what was fitted on
      what, before which split) plus a runtime hashing mode; published tools are too heavy
      to reuse.
    EVERSE: indicator ``functional_correctness`` (asks for a quantifiable correctness
      measure -- leakage invalidates it); RSQKit
      https://everse.software/RSQKit/testing_software .
    """

    name = "leakage"
    description = "train/test leakage: preprocessing before split, overlap, reuse"
    tier, effort, proposal = "B", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.7"
    difficulty = 4
    hooks = ("stochastic", "statistical", "unit_of_analysis")
    tools = ("leakage-analysis (optional)",)


class InferenceLedgerAnalyzer(ResponsibleRSEStub):
    """TODO (Tier B, M): the garden of forking paths, measured at runtime.

    During a run, wrap ``scipy.stats`` / ``statsmodels`` / ``pingouin`` test functions
    (only when enabled) and record every test: statistic, df, p, calling function.
    Findings: k tests on one outcome without a multiple-comparison correction; p without
    effect size and CI in the same output; tests run vs. tests reported;
    statcheck-style recomputation of p from statistic and df. Static extra: optional
    stopping (test inside a loop that breaks on ``p < alpha``).
    Tools: statsmodels ``multipletests``, scipy.
    Difficulty: 5/5 (~5 h/week) -- runtime instrumentation of three statistics libraries,
      matching tests to reported outputs, and statcheck-style recomputation --
      research-level.
    EVERSE: indicator ``functional_correctness`` only; no EVERSE indicator covers
      inferential practice (multiple testing, forking paths).
    """

    name = "inference_ledger"
    description = "all hypothesis tests actually run vs. those corrected and reported"
    when = "runtime"
    tier, effort, proposal = "B", "M", "RESPONSIBLE_RSE_PLUGINS.md §2.8"
    difficulty = 5
    hooks = ("statistical",)
    tools = ("statsmodels", "scipy")
