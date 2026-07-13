"""Static (AST) annotation coverage: what is annotated, and what should be.

The runner in :mod:`rse_annotations.runner` works by *reflection*: the decorators
register themselves at import time, so it can only ever see functions that are
**already annotated**, in modules that **import cleanly**. Coverage is the opposite
question -- *which functions are missing an annotation?* -- so it cannot use the
registry at all:

* an unannotated function never enters the registry, by construction; and
* research code frequently refuses to import (a missing optional dependency, a
  module that calls ``sys.exit()`` at the bottom, an API key read at import time).

So this module never imports the target. It parses every ``*.py`` file under the
root with :mod:`ast`, walks the module/class/function structure, and reports:

1. **coverage** -- every function and method found, whether it carries one of the
   four annotations, aggregated per kind and per file; and
2. **candidates** -- for each *unannotated* function, the annotation it most likely
   deserves, inferred from the same syntactic heuristics the placement checks use
   (:mod:`rse_annotations.checks`): a file write implies ``@data_output``, a file
   read implies ``@data_input``, pure arithmetic implies ``@functional``, and an
   argument-in/value-out transform implies ``@mapping``; and
3. **audit hazards** -- a second, *orthogonal* axis (see ``PROPOSED_ANNOTATIONS.md``).
   The four annotations answer *where does data flow?*. They cannot express *"this
   answer came from a language model"*, *"this result depends on an RNG"* or *"this
   decides who is in the sample"* -- which is what a reviewer actually attacks. So a
   function has one dataflow role and, independently, zero or more hazards
   (:data:`HAZARDS`). These are **detected, not enforced**: the point is to show how
   much of a codebase is a reproducibility risk rather than plumbing, *before*
   committing to new decorators.

The suggestions are heuristic and deliberately conservative -- they are a worklist
for a human reviewer, not a verdict. Anything that is neither pure nor a transform
nor a boundary (CLI glue, orchestration, ``main()``) is reported as *not a
candidate*, with the reason, so the coverage denominator stays honest.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .checks import _called_names, _is_read_name, _is_write_name
from .discovery import _iter_python_files, _module_name_for
from .registry import KINDS

#: Names that *look* like reads/writes to the boundary heuristics but are really
#: in-memory conversions (``json.loads``, ``df.to_dict``, ``pd.to_numeric``, ...).
#: Without this the ``read_``/``to_`` prefix rules would label half of pandas as I/O.
_NOT_FILE_IO = {
    "loads", "dumps", "input", "flush", "send", "recv",
    "to_dict", "to_list", "to_numpy", "to_string", "to_frame", "to_records",
    "to_datetime", "to_numeric", "to_timedelta", "to_series", "to_set", "to_tuple",
    "to_bytes", "to_pydatetime", "load_dotenv",
}

#: Method names that mean I/O only *sometimes*: ``x.write(...)`` is a file if ``x`` is
#: a file, and a logger / socket / StringIO otherwise. We still count them, but never
#: with high confidence -- the reviewer has to look.
_GENERIC_IO = {"write", "read", "writelines", "readline", "readlines"}

#: Calls a ``@functional`` body may make and still count as pure maths. Anything
#: else means the body does *work* we cannot vouch for symbolically.
_MATH_SAFE = {
    "abs", "min", "max", "sum", "len", "round", "pow", "divmod",
    "float", "int", "bool", "range", "enumerate", "zip", "sorted", "isnan",
    "sqrt", "log", "log2", "log10", "exp", "sin", "cos", "tan", "floor", "ceil",
    "mean", "median", "std", "var", "array", "asarray", "zeros", "ones", "dot",
    "isclose", "sign", "prod", "clip", "nan_to_num", "count_nonzero", "unique",
}

#: Files we never count: test modules and pytest bootstrap.
_SKIP_FILE_PREFIXES = ("test_",)
_SKIP_FILE_NAMES = {"conftest.py", "setup.py"}

#: Candidate kinds, most audit-relevant first (drives the worklist ordering).
_KIND_PRIORITY = {"functional": 0, "data_output": 1, "data_input": 2, "mapping": 3}


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


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #

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


@dataclass
class FunctionRecord:
    """One function or method found by the static scan.

    Attributes:
        name: The function's own name.
        qualname: Dotted name within its module, e.g. ``RateLimiter.wait_if_needed``.
        module: Dotted module name derived from the scanned root.
        file: Absolute path to the source file.
        lineno: 1-based line of the ``def``.
        kind: The annotation actually present (one of :data:`~rse_annotations.registry.KINDS`),
            or ``None`` if the function is unannotated.
        suggested: The annotation this function looks like it deserves, or ``None``
            if it is not a candidate (procedural glue, a dunder, a nested helper).
        reason: Why ``suggested`` was chosen -- or why nothing was.
        confidence: ``"high"``, ``"medium"`` or ``"low"``.
        eligible: False for things an annotation would be meaningless on (dunders,
            nested closures, test helpers). Excluded from the coverage denominator.
        skip_reason: Why ``eligible`` is False.
        class_name: Owning class, if this is a method.
        has_docstring: Whether the function has a docstring (audit signal in itself).
        hazards: Audit hazards found in the body (see :class:`Hazard`). Independent of
            ``kind``/``suggested``: annotated functions can carry hazards too.
        calls: Names this function calls (used to propagate hazards through the tree).
    """

    name: str
    qualname: str
    module: str
    file: str
    lineno: int
    kind: Optional[str] = None
    suggested: Optional[str] = None
    reason: str = ""
    confidence: str = "low"
    eligible: bool = True
    skip_reason: str = ""
    class_name: Optional[str] = None
    has_docstring: bool = False
    hazards: List[Hazard] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)

    @property
    def annotated(self) -> bool:
        return self.kind is not None

    @property
    def is_candidate(self) -> bool:
        """Unannotated, eligible, and we have a concrete kind to propose."""
        return self.eligible and self.kind is None and self.suggested is not None

    @property
    def location(self) -> str:
        return f"{self.file}:{self.lineno}"

    @property
    def hazard_kinds(self) -> List[str]:
        return [h.kind for h in self.hazards]

    def hazard(self, kind: str) -> Optional[Hazard]:
        for h in self.hazards:
            if h.kind == kind:
                return h
        return None


@dataclass
class CoverageReport:
    """The result of a static scan of a research-software tree."""

    root: Path
    records: List[FunctionRecord] = field(default_factory=list)
    files_scanned: int = 0
    parse_errors: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def eligible(self) -> List[FunctionRecord]:
        return [r for r in self.records if r.eligible]

    @property
    def annotated(self) -> List[FunctionRecord]:
        return [r for r in self.records if r.annotated]

    @property
    def candidates(self) -> List[FunctionRecord]:
        """Unannotated functions worth annotating, most audit-relevant first."""
        cands = [r for r in self.records if r.is_candidate]
        return sorted(cands, key=lambda r: (_KIND_PRIORITY.get(r.suggested, 9),
                                            r.file, r.lineno))

    @property
    def coverage(self) -> float:
        """Fraction of *eligible* functions that carry an annotation (0.0--1.0)."""
        n = len(self.eligible)
        return (len(self.annotated) / n) if n else 0.0

    @property
    def hazardous(self) -> List[FunctionRecord]:
        """Eligible functions carrying at least one audit hazard, worst first."""
        hits = [r for r in self.eligible if r.hazards]
        return sorted(hits, key=lambda r: (min(_HAZARD_PRIORITY[h.kind] for h in r.hazards),
                                           r.file, r.lineno))

    def counts_by_kind(self) -> Dict[str, int]:
        return {k: sum(1 for r in self.records if r.kind == k) for k in KINDS}

    def suggested_by_kind(self) -> Dict[str, int]:
        return {k: sum(1 for r in self.candidates if r.suggested == k) for k in KINDS}

    def counts_by_hazard(self) -> Dict[str, int]:
        return {h: sum(1 for r in self.eligible if r.hazard(h)) for h in HAZARDS}

    @property
    def hazard_rate(self) -> float:
        """Fraction of *eligible* functions that are a hazard rather than plumbing."""
        n = len(self.eligible)
        return (len(self.hazardous) / n) if n else 0.0

    def by_file(self) -> Dict[str, List[FunctionRecord]]:
        out: Dict[str, List[FunctionRecord]] = {}
        for r in self.records:
            out.setdefault(r.file, []).append(r)
        return out


# --------------------------------------------------------------------------- #
# Syntactic annotation detection
# --------------------------------------------------------------------------- #

def _dotted(node: ast.AST) -> str:
    """Render a decorator expression as a dotted name (``a.b.c``), best effort."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    return ""


def _alias_map(tree: ast.Module) -> Dict[str, str]:
    """Map the local names that refer to our decorators onto their kind.

    Handles ``from rse_annotations import functional``, ``... import functional as pure``
    and ``import rse_annotations`` (used as ``@rse_annotations.functional``).
    """
    aliases: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "rse_annotations" or mod.startswith("rse_annotations."):
                for a in node.names:
                    if a.name in KINDS:
                        aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "rse_annotations":
                    # qualified use: <local>.functional
                    for kind in KINDS:
                        aliases[f"{a.asname or a.name}.{kind}"] = kind
    return aliases


def _annotation_kind(node: ast.AST, aliases: Dict[str, str]) -> Optional[str]:
    """Return the rse annotation applied to ``node``, if any (bare or called form)."""
    for dec in getattr(node, "decorator_list", []):
        name = _dotted(dec)
        if name in aliases:
            return aliases[name]
        # Fall back to the bare kind name even without a recognised import: research
        # code is often copied around, and a literal @functional is unambiguous here.
        tail = name.rsplit(".", 1)[-1]
        if tail in KINDS:
            return tail
    return None


# --------------------------------------------------------------------------- #
# Candidate inference
# --------------------------------------------------------------------------- #

def _call_name(call: ast.Call) -> Optional[str]:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _open_mode(call: ast.Call) -> str:
    """The mode string passed to ``open(...)`` -- ``"r"`` if not given literally."""
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant) \
            and isinstance(call.args[1].value, str):
        return call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant) \
                and isinstance(kw.value.value, str):
            return kw.value.value
    return "r"


def _file_io_calls(node: ast.AST) -> Tuple[List[str], List[str]]:
    """Split the calls in ``node`` into (reads, writes), ignoring in-memory look-alikes.

    ``open`` is resolved by its *mode*: ``open(p, "w")`` is a write, not a read.
    """
    reads, writes = set(), set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        name = _call_name(n)
        if not name or name in _NOT_FILE_IO:
            continue
        if name == "open":
            mode = _open_mode(n)
            target = writes if any(c in mode for c in "wxa+") else reads
            target.add(f'open("{mode}")')
        elif _is_write_name(name):
            writes.add(name)
        elif _is_read_name(name):
            reads.add(name)
    return sorted(reads), sorted(writes)


def _returns_a_value(node: ast.AST) -> bool:
    """True if the body has a ``return <expr>`` (a bare ``return`` does not count)."""
    for n in ast.walk(node):
        if isinstance(n, ast.Return) and n.value is not None:
            return True
        if isinstance(n, (ast.Yield, ast.YieldFrom)):
            return True
    return False


def _param_names(node: ast.AST) -> List[str]:
    a = node.args
    names = [p.arg for p in (list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs))]
    if a.vararg:
        names.append(a.vararg.arg)
    if a.kwarg:
        names.append(a.kwarg.arg)
    return names


def _suggest(node: ast.AST) -> Tuple[Optional[str], str, str]:
    """Infer (kind, reason, confidence) for an unannotated function from its body."""
    called = _called_names(node)
    reads, writes = _file_io_calls(node)
    params = _param_names(node)
    returns = _returns_a_value(node)

    if reads and writes:
        return ("data_output",
                f"reads ({', '.join(reads[:3])}) *and* writes ({', '.join(writes[:3])}) "
                f"-- consider splitting into @data_input + @data_output",
                "low")
    if writes:
        specific = [w for w in writes if w not in _GENERIC_IO]
        conf = "high" if specific else "medium"
        hint = "" if specific else " (may be a logger/stream, not a file -- check)"
        return ("data_output",
                f"writes a file/sink: {', '.join(writes[:3])}{hint}", conf)
    if reads:
        specific = [r for r in reads if r not in _GENERIC_IO]
        conf = "high" if specific else "medium"
        hint = "" if specific else " (may be a logger/stream, not a file -- check)"
        return ("data_input",
                f"reads a file/source: {', '.join(reads[:3])}{hint}", conf)

    if not returns:
        return (None, "returns nothing and does no I/O: procedural glue (orchestration/CLI)", "")
    if not params:
        return (None, "returns a value but takes no input and does no I/O: "
                      "constant/config provider", "")

    if "print" in called:
        return ("mapping", "returns a value but also prints; report/format helper", "low")

    impure = sorted(n for n in called if n not in _MATH_SAFE)
    if not impure:
        conf = "high" if not called else "medium"
        detail = "arithmetic only" if not called else f"arithmetic + pure helpers ({', '.join(sorted(called)[:3])})"
        return ("functional", f"pure: {detail}, no I/O, returns a value", conf)

    return ("mapping",
            f"takes input, returns a transformed value, no I/O (calls {', '.join(impure[:3])})",
            "medium")


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
                            f"name suggests a reported statistic; verify it against its "
                            f"definition", "medium"))

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


# --------------------------------------------------------------------------- #
# The scan
# --------------------------------------------------------------------------- #

def _eligibility(name: str, class_name: Optional[str], depth: int) -> Tuple[bool, str]:
    if depth > 0:
        return False, "nested function (closure/local helper)"
    if name.startswith("__") and name.endswith("__"):
        return False, "dunder method"
    if name.startswith("test_"):
        return False, "test function"
    return True, ""


def _visit_body(body, *, module: str, file: str, aliases, records: List[FunctionRecord],
                class_name: Optional[str] = None, depth: int = 0,
                prefix: str = "") -> None:
    """Recursively collect every function/method under ``body``."""
    for node in body:
        if isinstance(node, ast.ClassDef):
            _visit_body(node.body, module=module, file=file, aliases=aliases,
                        records=records, class_name=node.name, depth=depth,
                        prefix=f"{prefix}{node.name}.")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            eligible, skip_reason = _eligibility(node.name, class_name, depth)
            kind = _annotation_kind(node, aliases)
            if kind is None and eligible:
                suggested, reason, confidence = _suggest(node)
            else:
                suggested, reason, confidence = None, "", ""
            # Hazards are orthogonal to the dataflow role, so they are computed for
            # *annotated* functions too -- `compute_dimension_icr` is a @mapping and a
            # statistical hazard at the same time.
            if eligible:
                reads, writes = _file_io_calls(node)
                hazards = _hazards(node, name=node.name, params=_param_names(node),
                                   returns=_returns_a_value(node),
                                   reads=reads, writes=writes)
            else:
                hazards = []
            records.append(FunctionRecord(
                name=node.name,
                qualname=f"{prefix}{node.name}",
                module=module,
                file=file,
                lineno=node.lineno,
                kind=kind,
                suggested=suggested,
                reason=reason,
                confidence=confidence,
                eligible=eligible,
                skip_reason=skip_reason,
                class_name=class_name,
                has_docstring=ast.get_docstring(node) is not None,
                hazards=hazards,
                calls=sorted(_called_names(node)),
            ))
            # descend for nested defs (recorded, but never eligible)
            _visit_body(node.body, module=module, file=file, aliases=aliases,
                        records=records, class_name=class_name, depth=depth + 1,
                        prefix=f"{prefix}{node.name}.")


def _skip_file(path: Path) -> bool:
    return (path.name in _SKIP_FILE_NAMES
            or path.name.startswith(_SKIP_FILE_PREFIXES))


def scan_path(root) -> CoverageReport:
    """Statically scan ``root`` and report annotation coverage plus candidates.

    Nothing is imported and nothing is executed -- the tree is parsed with
    :mod:`ast` only, so this works on code that cannot be imported at all.

    Args:
        root: Directory of research software to scan (``str`` or ``Path``).

    Returns:
        A :class:`CoverageReport` holding one :class:`FunctionRecord` per function
        and method found (test modules, caches and vendored directories excluded).
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory")

    report = CoverageReport(root=root)
    for path in sorted(_iter_python_files(root)):
        if _skip_file(path):
            continue
        report.files_scanned += 1
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            report.parse_errors.append((str(path), repr(exc)))
            continue
        _visit_body(tree.body,
                    module=_module_name_for(path, root),
                    file=str(path),
                    aliases=_alias_map(tree),
                    records=report.records)

    # Both of these need the whole tree, so they run once the walk is complete.
    _propagate_hazards(report.records)
    _flag_uncalled_validations(report.records)
    return report


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _table(headers: List[str], rows: List[List[str]]) -> str:
    """Render a fixed-width text table (no dependencies)."""
    if not rows:
        return "  (none)"
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip()
    rule = "  ".join("-" * w for w in widths).rstrip()
    out = [line, rule]
    for row in rows:
        out.append("  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip())
    return "\n".join(out)


def _rel(report: CoverageReport, file: str) -> str:
    try:
        return str(Path(file).relative_to(report.root)).replace("\\", "/")
    except ValueError:
        return file


def _critical_hazard(rec: FunctionRecord) -> Optional[Hazard]:
    """The record's worst *direct* provenance hazard, or ``None``.

    Inherited (``indirect``) hazards are excluded on purpose: propagation is what makes
    the map complete, and a shortlist is only useful if it names the function that
    actually does the dangerous thing.
    """
    for kind in CRITICAL_HAZARDS:
        h = rec.hazard(kind)
        if h is not None and not h.indirect:
            return h
    return None


def render_coverage_text(report: CoverageReport, *, max_candidates: int = 25) -> str:
    """Render the coverage table and candidate worklist for the console."""
    eligible, annotated = len(report.eligible), len(report.annotated)
    lines = [
        f"Annotation coverage for {report.root}",
        f"  {report.files_scanned} file(s), {len(report.records)} function(s)/method(s) found; "
        f"{eligible} eligible (dunders, nested helpers and tests excluded)",
        f"  annotated: {annotated}/{eligible}  ({report.coverage:.0%})",
        "",
        "By annotation kind",
    ]
    present, suggested = report.counts_by_kind(), report.suggested_by_kind()
    lines.append(_table(
        ["kind", "annotated", "candidates"],
        [[f"@{k}", str(present[k]), str(suggested[k])] for k in KINDS],
    ))

    lines += ["", "By file"]
    rows = []
    for file, recs in sorted(report.by_file().items()):
        elig = [r for r in recs if r.eligible]
        ann = [r for r in recs if r.annotated]
        cand = [r for r in recs if r.is_candidate]
        if not elig:
            continue
        pct = f"{len(ann) / len(elig):.0%}"
        rows.append([_rel(report, file), str(len(elig)), str(len(ann)), pct, str(len(cand))])
    lines.append(_table(["file", "funcs", "annotated", "coverage", "candidates"], rows))

    if report.hazardous:
        haz = report.counts_by_hazard()
        lines += ["", f"Audit hazards ({len(report.hazardous)}/{eligible} eligible functions, "
                      f"{report.hazard_rate:.0%})",
                  "  Orthogonal to the four annotations: not 'where does data flow?' but",
                  "  'where can the result be wrong, and can I reproduce it?' (proposed, not yet enforced)"]
        lines.append(_table(
            ["hazard", "n", "specialises", "what it means"],
            [[f"@{h}", str(haz[h]),
              f"@{HAZARD_PARENT[h]}" if HAZARD_PARENT[h] else "--",
              HAZARD_HELP[h]] for h in HAZARDS if haz[h]],
        ))

        worst = [r for r in report.hazardous if _critical_hazard(r)]
        if worst:
            lines += ["", f"Reproducibility-critical ({len(worst)})"]
            lines.append(_table(
                ["hazards", "function", "location", "why"],
                [[",".join(h.kind for h in r.hazards), r.qualname,
                  f"{_rel(report, r.file)}:{r.lineno}",
                  _critical_hazard(r).reason] for r in worst[:max_candidates]],
            ))
            if len(worst) > max_candidates:
                lines.append(f"  ... and {len(worst) - max_candidates} more (see the written report)")

    cands = report.candidates
    lines += ["", f"Candidates for annotation ({len(cands)})"]
    shown = cands[:max_candidates]
    lines.append(_table(
        ["suggest", "conf", "function", "location", "why"],
        [[f"@{c.suggested}", c.confidence, c.qualname,
          f"{_rel(report, c.file)}:{c.lineno}", c.reason] for c in shown],
    ))
    if len(cands) > len(shown):
        lines.append(f"  ... and {len(cands) - len(shown)} more (see the written report)")

    if report.parse_errors:
        lines += ["", f"Could not parse {len(report.parse_errors)} file(s):"]
        lines += [f"  {_rel(report, f)}: {e}" for f, e in report.parse_errors]
    return "\n".join(lines)


def render_coverage_markdown(report: CoverageReport) -> str:
    """Render the full report (every candidate, no truncation) as Markdown."""
    eligible, annotated = len(report.eligible), len(report.annotated)
    present, suggested = report.counts_by_kind(), report.suggested_by_kind()

    out = [
        "# Annotation coverage",
        "",
        f"Static (AST) scan of `{report.root}` — nothing imported, nothing executed.",
        "",
        f"- files scanned: **{report.files_scanned}**",
        f"- functions/methods found: **{len(report.records)}** "
        f"({eligible} eligible; dunders, nested helpers and tests excluded)",
        f"- annotated: **{annotated}/{eligible}** (**{report.coverage:.0%}** coverage)",
        f"- candidates for annotation: **{len(report.candidates)}**",
        "",
        "## Coverage by kind",
        "",
        "| Annotation | Present | Candidates |",
        "| --- | ---: | ---: |",
    ]
    out += [f"| `@{k}` | {present[k]} | {suggested[k]} |" for k in KINDS]

    out += ["", "## Coverage by file", "",
            "| File | Functions | Annotated | Coverage | Candidates |",
            "| --- | ---: | ---: | ---: | ---: |"]
    for file, recs in sorted(report.by_file().items()):
        elig = [r for r in recs if r.eligible]
        if not elig:
            continue
        ann = [r for r in recs if r.annotated]
        cand = [r for r in recs if r.is_candidate]
        out.append(f"| `{_rel(report, file)}` | {len(elig)} | {len(ann)} | "
                   f"{len(ann) / len(elig):.0%} | {len(cand)} |")

    if report.annotated:
        out += ["", "## Already annotated", "",
                "| Function | File | Annotation |", "| --- | --- | --- |"]
        for r in sorted(report.annotated, key=lambda r: (r.file, r.lineno)):
            out.append(f"| `{r.qualname}` | `{_rel(report, r.file)}:{r.lineno}` | `@{r.kind}` |")

    if report.hazardous:
        haz = report.counts_by_hazard()
        out += ["", "## Audit hazards", "",
                "A second, **orthogonal** axis (proposed — detected here, not yet enforced). The "
                "four annotations answer *where does data flow?*; these answer *where can the "
                "result be wrong, and can I reproduce it?* A function has one dataflow role and "
                "zero or more hazards.", "",
                f"**{len(report.hazardous)} of {eligible}** eligible functions "
                f"(**{report.hazard_rate:.0%}**) carry at least one hazard.", "",
                "| Hazard | Found | Specialises | What it means |",
                "| --- | ---: | --- | --- |"]
        for h in HAZARDS:
            parent = f"`@{HAZARD_PARENT[h]}`" if HAZARD_PARENT[h] else "—"
            out.append(f"| `@{h}` | {haz[h]} | {parent} | {HAZARD_HELP[h]} |")

        out += ["", "### Hazardous functions", "",
                "`indirect` means the hazard was inherited through the call graph — the "
                "function does not touch the model/RNG itself, but everything it returns "
                "depends on one.", "",
                "| Hazards | Function | Location | Role | Evidence |",
                "| --- | --- | --- | --- | --- |"]
        for r in report.hazardous:
            kinds = ", ".join(f"`@{h.kind}`" + ("*" if h.indirect else "")
                              for h in sorted(r.hazards, key=lambda x: _HAZARD_PRIORITY[x.kind]))
            role = f"`@{r.kind}`" if r.kind else (f"`@{r.suggested}`?" if r.suggested else "—")
            why = "; ".join(h.reason for h in sorted(
                r.hazards, key=lambda x: _HAZARD_PRIORITY[x.kind])[:2])
            out.append(f"| {kinds} | `{r.qualname}` | `{_rel(report, r.file)}:{r.lineno}` | "
                       f"{role} | {why} |")
        out += ["", "`*` = inherited through the call graph (indirect)."]

    out += ["", "## Candidates", "",
            "Heuristic suggestions from the syntax alone — a worklist for review, "
            "not a verdict.", "",
            "| Suggested | Confidence | Function | Location | Why |",
            "| --- | --- | --- | --- | --- |"]
    for c in report.candidates:
        out.append(f"| `@{c.suggested}` | {c.confidence} | `{c.qualname}` | "
                   f"`{_rel(report, c.file)}:{c.lineno}` | {c.reason} |")

    skipped = [r for r in report.records
               if r.eligible and r.kind is None and r.suggested is None]
    if skipped:
        out += ["", "## Not candidates", "",
                "Eligible functions we deliberately do *not* propose an annotation for.",
                "", "| Function | Location | Reason |", "| --- | --- | --- |"]
        for r in sorted(skipped, key=lambda r: (r.file, r.lineno)):
            out.append(f"| `{r.qualname}` | `{_rel(report, r.file)}:{r.lineno}` | {r.reason} |")

    if report.parse_errors:
        out += ["", "## Parse errors", ""]
        out += [f"- `{_rel(report, f)}`: {e}" for f, e in report.parse_errors]

    return "\n".join(out) + "\n"
