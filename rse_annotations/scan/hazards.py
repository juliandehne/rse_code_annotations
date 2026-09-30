"""Audit hazards: the second, orthogonal axis of the static scan.

The dataflow decorators answer *where does data flow?*. These answer *where can the
result be wrong, and can I reproduce it?*. A function has one dataflow role and,
independently, zero or more hazards: an LLM call, an RNG, a sampling decision. They
are **detected, not enforced** -- a hazard *map*, so you can see how much of a
codebase is a reproducibility risk rather than plumbing.

Each hazard kind is one :class:`HazardKind` object (name, parent decorator, help text,
detector), listed in :data:`HAZARD_KINDS`. A new hazard is a detector function plus
one entry there. The names that count as evidence live in :mod:`.vocabulary`.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set, Tuple

from ..decorators.markers import HazardDecorator
from . import vocabulary as vocab
from .ast_utils import _call_name, _called_names, _dotted

if TYPE_CHECKING:
    from .model import FunctionRecord


# --------------------------------------------------------------------------- #
# What the detectors see, and what they report
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class FunctionView:
    """Everything a detector needs to know about one function body."""

    node: ast.AST
    name: str                 # lower-cased function name
    params: List[str]
    returns: bool
    reads: List[str]
    writes: List[str]
    called: Set[str]          # bare call names: ``shuffle``
    dotted: List[str]         # dotted call paths: ``client.chat.completions.create``


@dataclass
class Hazard:
    """One audit hazard detected in a function body.

    Orthogonal to :attr:`FunctionRecord.concern`: a function has a *dataflow role* and,
    independently, zero or more *hazards*. ``compute_dimension_icr`` is a ``@mapping``
    **and** a ``statistical`` hazard; ``stratified_sample`` is ``stochastic`` **and**
    ``unit_of_analysis``.

    Attributes:
        kind: The :attr:`HazardKind.name`, e.g. ``"stochastic"``.
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
    def parent(self) -> Optional[HazardDecorator]:
        """The dataflow decorator this hazard specialises, if any."""
        kind = HAZARD_KIND.get(self.kind)
        return kind.parent if kind else None


#: What a detector returns when it fires: ``(reason, confidence)``.
Evidence = Tuple[str, str]


@dataclass(frozen=True)
class HazardKind:
    """One kind of hazard: what it is, what it refines, and how to detect it.

    ``parent`` is a *reference* to the dataflow decorator the hazard typically
    refines, not a superclass: hazards and decorators are independent axes, and a
    ``@mapping`` can carry a ``statistical`` hazard although ``statistical`` refines
    ``@functional``.

    Attributes:
        name: The hazard's name, used in reports and JSON.
        parent: The :class:`HazardDecorator` it refines, or ``None``.
        help: What a reviewer has to demand when the hazard is present.
        critical: Decides whether a result can be trusted and regenerated; carrying
            it directly puts a function on the reviewer's shortlist.
        contagious: Answers *where did this value come from?*, so a caller inherits
            it through the call graph (see :func:`_propagate_hazards`).
        detect: The detector: ``FunctionView -> Evidence | None``.
    """

    name: str
    parent: Optional[HazardDecorator]
    help: str
    critical: bool
    contagious: bool
    detect: Callable[[FunctionView], Optional[Evidence]]

    def check(self, view: FunctionView) -> Optional[Hazard]:
        """Run the detector on ``view``; a :class:`Hazard` if it fires."""
        evidence = self.detect(view)
        return Hazard(self.name, *evidence) if evidence else None


# --------------------------------------------------------------------------- #
# Helpers shared by the detectors
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
    if called & vocab.AGGREGATE_CALLS:
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
                 if isinstance(n, ast.Call) and (_call_name(n) or "") in vocab.RNG_CALLS]
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
            if any(any(tok in nm for tok in vocab.JITTER_NAMES) for nm in names):
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
        if any(tok in p.lower() for tok in vocab.SEED_PARAMS):
            return f"seed parameter `{p}`"
    for n in ast.walk(node):
        if isinstance(n, ast.keyword) and n.arg \
                and any(tok in n.arg.lower() for tok in vocab.SEED_PARAMS):
            return f"`{n.arg}=` passed through"
    return None


# --------------------------------------------------------------------------- #
# The detectors -- one per hazard kind
# --------------------------------------------------------------------------- #

def _detect_model_call(v: FunctionView) -> Optional[Evidence]:
    """An answer entered the study from a language model."""
    hits = sorted({d for d in v.dotted if any(t in d.lower() for t in vocab.MODEL_TOKENS)}
                  | (v.called & vocab.MODEL_CALLS))
    if hits:
        return f"calls a language model: {', '.join(hits[:2])}", "high"
    return None


def _detect_human_input(v: FunctionView) -> Optional[Evidence]:
    """An answer entered the study from a *person*.

    The sibling of ``model_call`` under ``@data_input``: in an AI-assisted study every
    datum was produced by a model or by a person, and an audit has to be able to say
    which. It fires only when a human-source marker co-occurs with an actual read --
    ``human_input`` refines ``@data_input``, so something must come *in*.
    """
    files = sorted({s for s in _path_literals(v.node)
                    if any(t in s.lower() for t in vocab.HUMAN_DATA_TOKENS)})
    named = any(t.strip("_") in v.name for t in vocab.HUMAN_DATA_TOKENS)
    if not (files or named) or not (v.reads or v.called & vocab.DATA_LOAD_CALLS):
        return None
    src = (f"reads human-coded data ({', '.join(files[:2])})" if files
           else "named for human-coded data and reads a source")
    return (f"{src} -- record the coders, the codebook version and an "
            f"inter-coder reliability figure", "high" if files else "medium")


def _detect_external_tool(v: FunctionView) -> Optional[Evidence]:
    """The computation left the process."""
    hits = sorted({d for d in v.dotted if any(t in d.lower() for t in vocab.SHELL_TOKENS)}
                  | (v.called & vocab.SHELL_CALLS))
    if not hits:
        return None
    shell_true = any(isinstance(n, ast.keyword) and n.arg == "shell"
                     and isinstance(n.value, ast.Constant) and n.value.value is True
                     for n in ast.walk(v.node))
    detail = f"shells out ({', '.join(hits[:2])})"
    if shell_true:
        detail += " with `shell=True`, so the *shell* is part of the method too"
    return (f"{detail} -- the tool and its **version** belong in the run's "
            f"provenance, and a missing binary must fail loudly", "high")


def _detect_stochastic(v: FunctionView) -> Optional[Evidence]:
    """The result depends on an RNG."""
    hits = sorted(v.called & vocab.RNG_CALLS)
    if not hits or _rng_is_only_jitter(v.node):
        return None
    seeded = _is_seeded(v.node, v.params)
    if seeded:
        return (f"draws on an RNG ({', '.join(hits[:3])}), seeded via {seeded} -- "
                f"pure given the seed, so it is checkable", "high")
    return (f"draws on an RNG ({', '.join(hits[:3])}) with **no seed parameter** -- "
            f"the result cannot be regenerated", "high")


def _detect_statistical(v: FunctionView) -> Optional[Evidence]:
    """This computes a number the paper reports."""
    hits = sorted({d for d in v.dotted if any(t in d.lower() for t in vocab.STATS_TOKENS)}
                  | (v.called & vocab.STATS_CALLS))
    if hits:
        return (f"computes a statistic via {', '.join(hits[:2])} -- pin it against a "
                f"reference implementation", "high")
    # A file boundary named after a statistic (``write_icr_outputs``,
    # ``load_icr_progress``) moves the number around; it does not compute it.
    named = any(t in v.name for t in vocab.STATS_NAME_HINTS)
    if (named and v.returns and not v.reads and not v.writes
            and _computes_a_number(v.node, v.called)):
        return "name suggests a reported statistic; verify it against its definition", "medium"
    return None


def _detect_unit_of_analysis(v: FunctionView) -> Optional[Evidence]:
    """This changes *which* units are in the sample."""
    hits = sorted(v.called & vocab.SUBSET_CALLS)
    named = any(t in v.name for t in vocab.SUBSET_NAME_HINTS)
    if hits and named:
        return (f"drops records ({', '.join(hits[:3])}) and is named like a selection "
                f"step -- every drop needs a reason", "high")
    if hits:
        return f"drops or subsets records ({', '.join(hits[:3])})", "medium"
    comp_filter = any(isinstance(n, ast.comprehension) and n.ifs for n in ast.walk(v.node))
    if comp_filter and v.returns and not v.reads and not v.writes:
        return ("filters in a comprehension (`[x for x in xs if ...]`) -- may change "
                "the sample size", "low")
    return None


def _detect_human_decision(v: FunctionView) -> Optional[Evidence]:
    """A person, not the machine, decided -- at run time."""
    hits = sorted(v.called & vocab.HUMAN_CALLS)
    if hits:
        return (f"asks a person ({', '.join(hits[:2])}) -- record the judgement, the "
                f"decider and the time", "high" if "input" in hits else "medium")
    return None


def _detect_validation(v: FunctionView) -> Optional[Evidence]:
    """A guard asserting a property of the data."""
    if not v.name.startswith(vocab.VALIDATION_PREFIXES):
        return None
    if any(isinstance(n, (ast.Raise, ast.Assert)) for n in ast.walk(v.node)):
        return "guards a data invariant (raises/asserts)", "high"
    return "named like a guard", "medium"


def _detect_config(v: FunctionView) -> Optional[Evidence]:
    """A threshold / hyperparameter / path.

    Exactly the "constant/config provider" shape `_suggest` already declines to
    decorate: a value out, nothing in, no I/O. The dataflow decorators are silent on
    these, but a hard-coded 0.67 cutoff is precisely what a replication needs.
    """
    if v.returns and not v.params and not v.reads and not v.writes:
        return ("returns a value with no inputs and no I/O: a threshold/parameter that "
                "belongs in the run's provenance record", "high" if not v.called else "medium")
    return None


# --------------------------------------------------------------------------- #
# The hazard kinds -- most audit-relevant first (drives ordering)
# --------------------------------------------------------------------------- #

MODEL_CALL = HazardKind(
    "model_call", HazardDecorator.DATA_INPUT,
    "output came from a language model: non-deterministic, unrepeatable, and not "
    "verifiable by reading the code",
    critical=True, contagious=True, detect=_detect_model_call)
HUMAN_INPUT = HazardKind(
    "human_input", HazardDecorator.DATA_INPUT,
    "data was produced by a person (coding/annotation/gold standard): needs coder "
    "identity, a codebook version, and an inter-coder reliability figure",
    critical=True, contagious=True, detect=_detect_human_input)
EXTERNAL_TOOL = HazardKind(
    "external_tool", None,   # computation leaves the process; it may read, write, both or neither
    "computation leaves the process (subprocess/shell): the tool and its **version** "
    "are part of the method and must be recorded",
    critical=True, contagious=True, detect=_detect_external_tool)
STOCHASTIC = HazardKind(
    "stochastic", HazardDecorator.FUNCTIONAL,   # a seeded sampler is pure -- of its inputs plus the seed
    "output depends on an RNG: reproducible only if the seed is an explicit parameter",
    critical=True, contagious=True, detect=_detect_stochastic)
STATISTICAL = HazardKind(
    "statistical", HazardDecorator.FUNCTIONAL,
    "computes a reported statistic: must be pinned against a reference implementation "
    "or cite its definition",
    critical=True, contagious=False, detect=_detect_statistical)
UNIT_OF_ANALYSIS = HazardKind(
    "unit_of_analysis", HazardDecorator.MAPPING,   # records in, fewer records out
    "changes which units are in the sample: every dropped record needs a reason",
    critical=False, contagious=False, detect=_detect_unit_of_analysis)
HUMAN_DECISION = HazardKind(
    "human_decision", None,
    "a person decides here, at run time: the judgement, the decider and the time must "
    "be recorded",
    critical=False, contagious=False, detect=_detect_human_decision)
VALIDATION = HazardKind(
    "validation", None,
    "asserts a property of the data: a guard nobody calls is worse than no guard",
    critical=False, contagious=False, detect=_detect_validation)
CONFIG = HazardKind(
    "config", None,
    "supplies a threshold/hyperparameter: must land in the run's provenance record",
    critical=False, contagious=False, detect=_detect_config)

#: The hazard kinds above, most audit-relevant first; add a new one here.
HAZARD_KINDS: Tuple[HazardKind, ...] = (
    MODEL_CALL, HUMAN_INPUT, EXTERNAL_TOOL, STOCHASTIC, STATISTICAL,
    UNIT_OF_ANALYSIS, HUMAN_DECISION, VALIDATION, CONFIG,
)

# Derived views, for lookups by name (reports, JSON, tests).
HAZARD_KIND: Dict[str, HazardKind] = {k.name: k for k in HAZARD_KINDS}
HAZARDS: Tuple[str, ...] = tuple(k.name for k in HAZARD_KINDS)
HAZARD_PARENT: Dict[str, Optional[HazardDecorator]] = {k.name: k.parent for k in HAZARD_KINDS}
HAZARD_HELP: Dict[str, str] = {k.name: k.help for k in HAZARD_KINDS}
CRITICAL_HAZARDS: Tuple[str, ...] = tuple(k.name for k in HAZARD_KINDS if k.critical)
_HAZARD_PRIORITY = {name: i for i, name in enumerate(HAZARDS)}


# --------------------------------------------------------------------------- #
# Running the detectors
# --------------------------------------------------------------------------- #

def _hazards(node: ast.AST, *, name: str, params: List[str],
             returns: bool, reads: List[str], writes: List[str]) -> List[Hazard]:
    """Detect the audit hazards in one function body (see :data:`HAZARD_KINDS`)."""
    view = FunctionView(node=node, name=name.lower(), params=params, returns=returns,
                        reads=reads, writes=writes, called=_called_names(node),
                        dotted=_dotted_calls(node))
    return [h for kind in HAZARD_KINDS if (h := kind.check(view))]


def _propagate_hazards(records: List[FunctionRecord], rounds: int = 4) -> None:
    """Push the *contagious* hazards up the call graph.

    ``classify_paper`` does not itself touch the OpenAI client -- it calls
    ``_complete_with_retries``, which does. The function you actually want to decorate
    is the caller, so a hazard is inherited (at lower confidence) by anything that
    calls a hazardous function. Matching is by bare name, so a collision across two
    modules can over-report; that is why inherited hazards are marked ``indirect``.

    Only the hazards that answer *"where did this value come from?"* travel
    (:attr:`HazardKind.contagious`). ``config`` and ``validation`` are properties of
    the function itself and do not contaminate a caller.
    """
    contagious = [k.name for k in HAZARD_KINDS if k.contagious]
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
        h = rec.hazard(VALIDATION.name)
        if h and rec.name not in all_calls:
            h.reason += " -- **never called anywhere in the tree**: a guard nobody invokes"
            h.confidence = "high"
