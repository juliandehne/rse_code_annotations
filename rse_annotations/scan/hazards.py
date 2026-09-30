"""Audit hazards: the second, orthogonal axis of the static scan.

The four annotations answer *where does data flow?*. A function has one dataflow
role and, independently, zero or more hazards (:data:`HAZARDS`): an LLM call, an
RNG, a sampling decision. They are **detected, not enforced**.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Set

from .ast_utils import _call_name, _called_names, _dotted

if TYPE_CHECKING:
    from .model import FunctionRecord

# --------------------------------------------------------------------------- #
# Audit hazards -- the *second* axis (see PROPOSED_ANNOTATIONS.md)
#
# The four annotations answer "where does data flow?". These answer "where can the
# result be wrong, and can I reproduce it?". They are detected here but not yet
# enforced: this is a hazard *map*, so you can see how much of a codebase is a
# reproducibility risk rather than plumbing, before committing to new decorators.
# --------------------------------------------------------------------------- #

#: Hazard kinds, most audit-relevant first (drives ordering).
HAZARDS = (
    "model_call",       # an answer came from a language model
    "human_input",      # an answer came from a *person* (coding / annotation / gold standard)
    "external_tool",    # the computation left the process (subprocess / shell / CLI)
    "stochastic",       # the result depends on an RNG
    "statistical",      # this computes a number the paper reports
    "unit_of_analysis", # this changes *which* units are in the sample
    "human_decision",   # a person, not the machine, decided -- at run time
    "validation",       # a guard asserting a property of the data
    "config",           # a threshold / hyperparameter / path
)

#: Which dataflow annotation each hazard *specialises*, if any. ``@stochastic`` and
#: ``@statistical`` are refinements of ``@functional``: a properly seeded sampler is
#: still a pure function -- of its inputs *plus the seed*. ``@model_call`` and
#: ``@human_input`` are the two refinements of ``@data_input`` -- in an AI-assisted study
#: every datum was produced by a model or by a person, and the taxonomy must be able to
#: say which. ``@unit_of_analysis`` refines ``@mapping`` (records in, fewer records out).
#: ``@external_tool`` has no dataflow parent: computation *leaves the process*, and the
#: subprocess may read, write, both or neither.
HAZARD_PARENT: Dict[str, Optional[str]] = {
    "stochastic": "functional",
    "statistical": "functional",
    "model_call": "data_input",
    "human_input": "data_input",
    "unit_of_analysis": "mapping",
    "external_tool": None,
    "human_decision": None,
    "validation": None,
    "config": None,
}

HAZARD_HELP: Dict[str, str] = {
    "model_call": "output came from a language model: non-deterministic, unrepeatable, and not verifiable by reading the code",
    "human_input": "data was produced by a person (coding/annotation/gold standard): needs coder identity, a codebook version, and an inter-coder reliability figure",
    "external_tool": "computation leaves the process (subprocess/shell): the tool and its **version** are part of the method and must be recorded",
    "stochastic": "output depends on an RNG: reproducible only if the seed is an explicit parameter",
    "statistical": "computes a reported statistic: must be pinned against a reference implementation or cite its definition",
    "unit_of_analysis": "changes which units are in the sample: every dropped record needs a reason",
    "human_decision": "a person decides here, at run time: the judgement, the decider and the time must be recorded",
    "validation": "asserts a property of the data: a guard nobody calls is worse than no guard",
    "config": "supplies a threshold/hyperparameter: must land in the run's provenance record",
}

_HAZARD_PRIORITY = {h: i for i, h in enumerate(HAZARDS)}

#: The hazards that decide whether a *result* can be trusted and regenerated: it came
#: from a model, from a person, from another process, from an RNG, or it *is* a number
#: the paper prints. Carrying one of these directly (not inherited) puts a function on
#: the shortlist a reviewer would ask for first.
CRITICAL_HAZARDS = ("model_call", "human_input", "external_tool", "stochastic",
                    "statistical")

#: Calls that draw on a random source. ``Random`` catches ``random.Random(seed)``.
_RNG_CALLS = {
    "random", "randint", "randrange", "choice", "choices", "shuffle", "sample",
    "uniform", "gauss", "normalvariate", "randn", "rand", "permutation",
    "default_rng", "seed", "Random", "getrandbits", "randbytes", "uuid4",
    "token_hex", "token_bytes", "train_test_split",
}
#: Parameter names that mean "the caller controls the randomness".
_SEED_PARAMS = ("seed", "rng", "random_state", "generator")
#: Variable names that mean the RNG draw is a retry backoff, not a result.
_JITTER_NAMES = ("wait", "backoff", "jitter", "delay", "sleep", "pause", "retry")

#: Dotted fragments that mean a language-model client is being called.
_MODEL_TOKENS = (
    "openai", "anthropic", "litellm", "ollama", "cohere", "mistral",
    "chat.completions", "messages.create", "completions.create",
    "chat.complete", "generate_content", "transformers", "huggingface",
)
#: Bare call names that construct or invoke a model client.
_MODEL_CALLS = {"OpenAI", "AzureOpenAI", "Anthropic", "ChatCompletion", "ChatOpenAI"}

#: Markers, in a string literal or a function name, of data a *person* produced.
#:
#: Deliberately **not** "annotation": in the testbed that word names the LLM's own output
#: (``annotations_<tag>_checkpoint.csv``), while the human-coded files are ``coding_*.csv``
#: and ``gold_human_*.csv``. A token that means "human" in one project and "model" in the
#: next is not evidence. These name a person's judgement in the coding/content-analysis
#: sense, which is the tradition the term comes from.
_HUMAN_DATA_TOKENS = ("coding_", "coder", "codebook", "gold_human", "goldstandard",
                      "gold_standard", "human_label", "manual_", "adjudicat", "consensus",
                      "ground_truth")
#: Calls that pull records in from disk -- ``@human_input`` refines ``@data_input``, so
#: something must actually be read.
_READ_CALLS = {"read_csv", "read_excel", "read_json", "read_parquet", "read_text",
               "load", "loads", "glob", "rglob", "iterdir", "open", "readlines"}

#: The computation left the process. Matched against *dotted* calls, because ``run`` and
#: ``call`` as bare names are far too common to be evidence of anything. ``shutil.which``
#: counts: it is how code looks for a binary it is about to depend on.
_SHELL_TOKENS = ("subprocess.", "os.system", "os.popen", "os.spawn", "os.exec",
                 "shutil.which", "pexpect.", "plumbum.", "commands.getoutput")
#: Bare names that are unambiguous even without their module (``from subprocess import
#: Popen``). ``run`` and ``call`` are deliberately absent.
_SHELL_CALLS = {"Popen", "check_output", "check_call", "getoutput", "getstatusoutput"}

#: Statistics libraries: calling into one means a reported number is being computed.
_STATS_TOKENS = ("scipy.stats", "statsmodels", "sklearn.metrics", "krippendorff",
                 "pingouin", "numpy.corrcoef")
_STATS_CALLS = {
    "cohen_kappa_score", "f1_score", "accuracy_score", "precision_score",
    "recall_score", "roc_auc_score", "confusion_matrix", "pearsonr", "spearmanr",
    "kendalltau", "ttest_ind", "ttest_rel", "chi2_contingency", "mannwhitneyu",
    "wilcoxon", "corrcoef", "bootstrap",
}
#: Function-name fragments that name a statistic. Weaker evidence than a library call.
_STATS_NAME_HINTS = ("alpha", "kappa", "icr", "agreement", "reliability", "correlation",
                     "pvalue", "p_value", "ttest", "effect_size", "_stats", "significance")
#: Calls that aggregate many values into one -- the shape of computing a statistic.
_AGGREGATE_CALLS = {"mean", "median", "sum", "count", "std", "var", "min", "max", "len",
                    "value_counts", "nunique", "describe", "agg", "corr", "mode", "quantile"}

#: Calls that drop or subset records -- the sample changes size here.
_SUBSET_CALLS = {"drop", "dropna", "drop_duplicates", "query", "isin", "nlargest",
                 "nsmallest", "head", "tail", "truncate", "filter", "sample"}
#: Function-name fragments that announce a selection step.
_SUBSET_NAME_HINTS = ("filter", "select", "exclude", "subset", "narrow", "prune",
                      "restrict", "dedup", "sample", "shortlist")

#: Calls that hand the decision to a person.
_HUMAN_CALLS = {"input", "confirm", "prompt", "getpass"}

#: Function-name prefixes that announce a guard.
_VALIDATION_PREFIXES = ("check_", "validate_", "verify_", "ensure_", "assert_", "is_valid")


@dataclass
class Hazard:
    """One audit hazard detected in a function body.

    Orthogonal to :attr:`FunctionRecord.kind`: a function has a *dataflow role* and,
    independently, zero or more *hazards*. ``compute_dimension_icr`` is a ``@mapping``
    **and** a ``statistical`` hazard; ``stratified_sample`` is ``stochastic`` **and**
    ``unit_of_analysis``.

    Attributes:
        kind: One of :data:`HAZARDS`.
        reason: The evidence -- which calls, which parameters.
        confidence: ``"high"``, ``"medium"`` or ``"low"``.
        indirect: True if inferred through the call graph rather than seen directly
            (``classify_paper`` calls ``_complete_with_retries``, which calls the model).
    """

    kind: str
    reason: str
    confidence: str = "medium"
    indirect: bool = False

    @property
    def parent(self) -> Optional[str]:
        """The dataflow annotation this hazard specialises, if any."""
        return HAZARD_PARENT.get(self.kind)


# --------------------------------------------------------------------------- #
# Hazard detection
# --------------------------------------------------------------------------- #

def _dotted_calls(node: ast.AST) -> List[str]:
    """Every call in ``node`` rendered as a dotted name (``client.chat.completions.create``)."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            d = _dotted(n.func)
            if d:
                out.append(d)
    return out


def _computes_a_number(node: ast.AST, called: Set[str]) -> bool:
    """True if the body actually does arithmetic or aggregates values.

    Guards the ``statistical`` *name* hint. A function can carry ``icr`` or ``agreement``
    in its name and merely move the number around -- a fixture that builds a metrics
    frame, a menu prompt that asks whether to re-run the ICR pass. Computing a reported
    statistic means *computing*, so require the shape of a computation.
    """
    if called & _AGGREGATE_CALLS:
        return True
    arith = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Pow, ast.Mod)
    return any(isinstance(n, (ast.BinOp, ast.AugAssign)) and isinstance(n.op, arith)
               for n in ast.walk(node))


def _rng_is_only_jitter(node: ast.AST) -> bool:
    """True if the RNG only feeds a retry backoff, not the result.

    ``random.random()`` inside an exponential-backoff sleep is not a reproducibility
    hazard -- jitter in a wait interval cannot change a study's findings. Without this
    the retry helper of every API client is flagged ``stochastic``, and (worse) that
    false positive propagates up the call graph into the functions that *do* matter.

    The rule: every RNG call must be used either directly as an argument to ``sleep``,
    or to compute a value assigned to a wait/backoff/jitter/delay name.
    """
    rng_nodes = [n for n in ast.walk(node)
                 if isinstance(n, ast.Call) and (_call_name(n) or "") in _RNG_CALLS]
    if not rng_nodes:
        return False

    sheltered = set()
    for n in ast.walk(node):
        # sleep(<... rng ...>)
        if isinstance(n, ast.Call) and (_call_name(n) or "").endswith("sleep"):
            for sub in ast.walk(n):
                if isinstance(sub, ast.Call) and sub in rng_nodes:
                    sheltered.add(id(sub))
        # wait_s = backoff + backoff * 0.25 * random.random()
        if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)) and n.value is not None:
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            names = [t.id.lower() for t in targets if isinstance(t, ast.Name)]
            if any(any(tok in nm for tok in _JITTER_NAMES) for nm in names):
                for sub in ast.walk(n.value):
                    if isinstance(sub, ast.Call) and sub in rng_nodes:
                        sheltered.add(id(sub))

    return all(id(n) in sheltered for n in rng_nodes)


def _path_literals(node: ast.AST) -> Set[str]:
    """String literals in a body that could name a file, directory or glob.

    A *filename* is evidence about where data came from; a *sentence* about the data is
    not, and the whole point of the hazard axis is to stop trusting the prose. The first
    run of the human-source detector fired on three argparse ``help=`` strings and a
    ``print``, all of which merely mention the goldstandard -- so anything containing
    whitespace is rejected. F-string fragments survive: ``f"coding_{user}.csv"`` walks to
    the literal chunk ``coding_``, which is exactly the marker we want.
    """
    return {n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value and not any(c.isspace() for c in n.value)}


def _is_seeded(node: ast.AST, params: List[str]) -> Optional[str]:
    """How the caller controls this function's randomness, or ``None`` if it cannot.

    A properly seeded sampler is still a *pure* function -- of its inputs plus the
    seed -- which is exactly why the seed has to be reachable from the signature.
    """
    for p in params:
        if any(tok in p.lower() for tok in _SEED_PARAMS):
            return f"seed parameter `{p}`"
    for n in ast.walk(node):
        if isinstance(n, ast.keyword) and n.arg \
                and any(tok in n.arg.lower() for tok in _SEED_PARAMS):
            return f"`{n.arg}=` passed through"
    return None


def _hazards(node: ast.AST, *, name: str, params: List[str],
             returns: bool, reads: List[str], writes: List[str]) -> List[Hazard]:
    """Detect audit hazards in a function body (see :data:`HAZARDS`)."""
    called = _called_names(node)
    dotted = _dotted_calls(node)
    lname = name.lower()
    found: List[Hazard] = []

    # -- model_call: an answer entered the study from a language model -------- #
    model_hits = sorted({d for d in dotted
                         if any(t in d.lower() for t in _MODEL_TOKENS)}
                        | (called & _MODEL_CALLS))
    if model_hits:
        found.append(Hazard("model_call",
                            f"calls a language model: {', '.join(model_hits[:2])}",
                            "high"))

    # -- human_input: an answer entered the study from a *person* ------------- #
    # The sibling of ``model_call`` under ``@data_input``: in an AI-assisted study every
    # datum was produced by a model or by a person, and an audit has to be able to say
    # which. It fires only when a human-source marker co-occurs with an actual read --
    # ``@human_input`` refines ``@data_input``, so something must come *in*.
    human_files = sorted({s for s in _path_literals(node)
                          if any(t in s.lower() for t in _HUMAN_DATA_TOKENS)})
    human_name = any(t.strip("_") in lname for t in _HUMAN_DATA_TOKENS)
    if (human_files or human_name) and (reads or called & _READ_CALLS):
        src = (f"reads human-coded data ({', '.join(human_files[:2])})" if human_files
               else "named for human-coded data and reads a source")
        found.append(Hazard("human_input",
                            f"{src} -- record the coders, the codebook version and an "
                            f"inter-coder reliability figure",
                            "high" if human_files else "medium"))

    # -- external_tool: the computation left the process ---------------------- #
    shell_hits = sorted({d for d in dotted
                         if any(t in d.lower() for t in _SHELL_TOKENS)}
                        | (called & _SHELL_CALLS))
    if shell_hits:
        shell_true = any(isinstance(n, ast.keyword) and n.arg == "shell"
                         and isinstance(n.value, ast.Constant) and n.value.value is True
                         for n in ast.walk(node))
        detail = f"shells out ({', '.join(shell_hits[:2])})"
        if shell_true:
            detail += " with `shell=True`, so the *shell* is part of the method too"
        found.append(Hazard("external_tool",
                            f"{detail} -- the tool and its **version** belong in the run's "
                            f"provenance, and a missing binary must fail loudly",
                            "high"))

    # -- stochastic: the result depends on an RNG ----------------------------- #
    rng_hits = sorted(called & _RNG_CALLS)
    if rng_hits and not _rng_is_only_jitter(node):
        seeded = _is_seeded(node, params)
        if seeded:
            found.append(Hazard("stochastic",
                                f"draws on an RNG ({', '.join(rng_hits[:3])}), seeded via "
                                f"{seeded} -- pure given the seed, so it is checkable",
                                "high"))
        else:
            found.append(Hazard("stochastic",
                                f"draws on an RNG ({', '.join(rng_hits[:3])}) with **no seed "
                                f"parameter** -- the result cannot be regenerated",
                                "high"))

    # -- statistical: this computes a number the paper reports ---------------- #
    lib_hits = sorted({d for d in dotted if any(t in d.lower() for t in _STATS_TOKENS)}
                      | (called & _STATS_CALLS))
    name_hit = any(t in lname for t in _STATS_NAME_HINTS)
    if lib_hits:
        found.append(Hazard("statistical",
                            f"computes a statistic via {', '.join(lib_hits[:2])} -- pin it "
                            f"against a reference implementation", "high"))
    elif (name_hit and returns and not reads and not writes
            and _computes_a_number(node, called)):
        # A file boundary named after a statistic (``write_icr_outputs``,
        # ``load_icr_progress``) moves the number around; it does not compute it.
        found.append(Hazard("statistical",
                            "name suggests a reported statistic; verify it against its "
                            "definition", "medium"))

    # -- unit_of_analysis: this changes *which* units are in the sample ------- #
    subset_hits = sorted(called & _SUBSET_CALLS)
    name_subset = any(t in lname for t in _SUBSET_NAME_HINTS)
    comp_filter = any(isinstance(n, ast.comprehension) and n.ifs for n in ast.walk(node))
    if subset_hits and name_subset:
        found.append(Hazard("unit_of_analysis",
                            f"drops records ({', '.join(subset_hits[:3])}) and is named like a "
                            f"selection step -- every drop needs a reason", "high"))
    elif subset_hits:
        found.append(Hazard("unit_of_analysis",
                            f"drops or subsets records ({', '.join(subset_hits[:3])})", "medium"))
    elif comp_filter and returns and not reads and not writes:
        found.append(Hazard("unit_of_analysis",
                            "filters in a comprehension (`[x for x in xs if ...]`) -- may change "
                            "the sample size", "low"))

    # -- human_decision: a person, not the machine, decided ------------------- #
    human_hits = sorted(called & _HUMAN_CALLS)
    if human_hits:
        conf = "high" if "input" in human_hits else "medium"
        found.append(Hazard("human_decision",
                            f"asks a person ({', '.join(human_hits[:2])}) -- record the "
                            f"judgement, the decider and the time", conf))

    # -- validation: a guard asserting a property of the data ----------------- #
    raises = any(isinstance(n, (ast.Raise, ast.Assert)) for n in ast.walk(node))
    if lname.startswith(_VALIDATION_PREFIXES) and raises:
        found.append(Hazard("validation",
                            "guards a data invariant (raises/asserts)", "high"))
    elif lname.startswith(_VALIDATION_PREFIXES):
        found.append(Hazard("validation", "named like a guard", "medium"))

    # -- config: a threshold / hyperparameter / path -------------------------- #
    # Exactly the "constant/config provider" shape `_suggest` already declines to
    # annotate: a value out, nothing in, no I/O. The four annotations are silent on
    # these, but a hard-coded 0.67 cutoff is precisely what a replication needs.
    if returns and not params and not reads and not writes:
        found.append(Hazard("config",
                            "returns a value with no inputs and no I/O: a threshold/parameter "
                            "that belongs in the run's provenance record",
                            "high" if not called else "medium"))

    return found


def _propagate_hazards(records: List[FunctionRecord], rounds: int = 4) -> None:
    """Push the *provenance* hazards up the call graph.

    ``classify_paper`` does not itself touch the OpenAI client -- it calls
    ``_complete_with_retries``, which does. The function you actually want to annotate
    is the caller, so a hazard is inherited (at lower confidence) by anything that
    calls a hazardous function. Matching is by bare name, so a collision across two
    modules can over-report; that is why inherited hazards are marked ``indirect``.

    Only the four hazards that answer *"where did this value come from?"* travel:
    a model, a person, another process, or an RNG. ``@config`` and ``@validation`` are
    properties of the function itself and do not contaminate a caller.
    """
    contagious = ("model_call", "human_input", "external_tool", "stochastic")
    for _ in range(rounds):
        carriers = {h: {r.name for r in records if r.hazard(h)} for h in contagious}
        changed = False
        for rec in records:
            if not rec.eligible:
                continue
            for kind in contagious:
                if rec.hazard(kind):
                    continue
                via = sorted((set(rec.calls) & carriers[kind]) - {rec.name})
                if via:
                    rec.hazards.append(Hazard(
                        kind,
                        f"inherits `{kind}` from {', '.join(f'`{v}`' for v in via[:2])}",
                        "medium", indirect=True))
                    changed = True
        if not changed:
            break


def _flag_uncalled_validations(records: List[FunctionRecord]) -> None:
    """A guard nobody invokes is worse than no guard -- it looks like safety."""
    all_calls = {c for r in records for c in r.calls}
    for rec in records:
        h = rec.hazard("validation")
        if h and rec.name not in all_calls:
            h.reason += " -- **never called anywhere in the tree**: a guard nobody invokes"
            h.confidence = "high"
