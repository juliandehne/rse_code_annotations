"""@stochastic: the result depends on a random number generator."""
import ast

from .._base import Concern, call_name

RNG_CALLS = {
    "random", "randint", "randrange", "choice", "choices", "shuffle", "sample",
    "uniform", "gauss", "normalvariate", "randn", "rand", "permutation",
    "default_rng", "seed", "Random", "getrandbits", "randbytes", "uuid4",
    "token_hex", "token_bytes", "train_test_split",
}
SEED_PARAMS = ("seed", "rng", "random_state", "generator")
JITTER_NAMES = ("wait", "backoff", "jitter", "delay", "sleep", "pause", "retry")


def _only_jitter(node):
    """True if every RNG call only feeds a sleep or a wait/backoff variable (retry jitter)."""
    rng = {id(n) for n in ast.walk(node) if isinstance(n, ast.Call) and call_name(n) in RNG_CALLS}
    sheltered = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and (call_name(n) or "").endswith("sleep"):
            sheltered |= {id(s) for s in ast.walk(n)}
        elif isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)) and n.value is not None:
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            if any(isinstance(t, ast.Name) and any(j in t.id.lower() for j in JITTER_NAMES)
                   for t in targets):
                sheltered |= {id(s) for s in ast.walk(n.value)}
    return rng <= sheltered


def _seed(v):
    names = v.params + [n.arg for n in ast.walk(v.node) if isinstance(n, ast.keyword) and n.arg]
    return next((p for p in names if any(t in p.lower() for t in SEED_PARAMS)), None)


def detect(v):
    hits = sorted(v.called & RNG_CALLS)
    if not hits or _only_jitter(v.node):
        return None
    seed = _seed(v)
    if seed:
        return f"draws on an RNG ({', '.join(hits[:3])}), seeded via `{seed}`", "high"
    return f"draws on an RNG ({', '.join(hits[:3])}) with no seed parameter", "high"


CONCERN = Concern(
    "stochastic",
    "Output depends on an RNG: is the seed an explicit parameter, so the result can be regenerated?",
    detect, critical=True, contagious=True)
