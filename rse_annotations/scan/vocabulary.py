"""The vocabulary of the static scan: which names count as evidence of what.

Data only, no logic. The scan matches call names, dotted call paths, parameter
names, function names and string literals against these lists. To teach the scan a
new library (another LLM client, another statistics package), extend a list here;
the detection code in :mod:`.ast_utils`, :mod:`.candidates` and :mod:`.hazards`
stays unchanged.

Sets hold exact names; tuples hold fragments or prefixes, matched with ``in`` or
``str.startswith``.
"""

# --------------------------------------------------------------------------- #
# Files the scan skips
# --------------------------------------------------------------------------- #

#: Files we never count: test modules and pytest bootstrap.
SKIP_FILE_PREFIXES = ("test_",)
SKIP_FILE_NAMES = {"conftest.py", "setup.py"}


# --------------------------------------------------------------------------- #
# File I/O -- decides @data_input / @data_output
# --------------------------------------------------------------------------- #

#: Calls that indicate file / stream I/O -- used by the purity and boundary lints.
READ_CALLS = {"open", "read", "read_text", "read_bytes", "load", "loads", "readlines",
              "readline", "recv", "input"}
WRITE_CALLS = {"write", "writelines", "write_text", "write_bytes", "dump", "dumps",
               "save", "to_csv", "to_json", "send", "flush"}
#: Name *prefixes* that also indicate reads / writes (catches pandas & friends:
#: read_csv, read_parquet, to_csv, to_markdown, to_parquet, ...).
READ_PREFIXES = ("read_", "load_")
WRITE_PREFIXES = ("write_", "to_", "save_", "dump_")

#: Names that *look* like reads/writes to the boundary heuristics but are really
#: in-memory conversions (``json.loads``, ``df.to_dict``, ``pd.to_numeric``, ...).
#: Without this the ``read_``/``to_`` prefix rules would label half of pandas as I/O.
NOT_FILE_IO = {
    "loads", "dumps", "input", "flush", "send", "recv",
    "to_dict", "to_list", "to_numpy", "to_string", "to_frame", "to_records",
    "to_datetime", "to_numeric", "to_timedelta", "to_series", "to_set", "to_tuple",
    "to_bytes", "to_pydatetime", "load_dotenv",
}

#: Method names that mean I/O only *sometimes*: ``x.write(...)`` is a file if ``x`` is
#: a file, and a logger / socket / StringIO otherwise. We still count them, but never
#: with high confidence -- the reviewer has to look.
GENERIC_IO = {"write", "read", "writelines", "readline", "readlines"}


# --------------------------------------------------------------------------- #
# Purity -- decides @functional
# --------------------------------------------------------------------------- #

#: Calls a ``@functional`` body may make and still count as pure maths. Anything
#: else means the body does *work* we cannot vouch for symbolically.
MATH_SAFE = {
    "abs", "min", "max", "sum", "len", "round", "pow", "divmod",
    "float", "int", "bool", "range", "enumerate", "zip", "sorted", "isnan",
    "sqrt", "log", "log2", "log10", "exp", "sin", "cos", "tan", "floor", "ceil",
    "mean", "median", "std", "var", "array", "asarray", "zeros", "ones", "dot",
    "isclose", "sign", "prod", "clip", "nan_to_num", "count_nonzero", "unique",
}


# --------------------------------------------------------------------------- #
# Hazard evidence -- one block per hazard kind (see :mod:`.hazards`)
# --------------------------------------------------------------------------- #

# -- model_call ------------------------------------------------------------- #
#: Dotted fragments that mean a language-model client is being called.
MODEL_TOKENS = (
    "openai", "anthropic", "litellm", "ollama", "cohere", "mistral",
    "chat.completions", "messages.create", "completions.create",
    "chat.complete", "generate_content", "transformers", "huggingface",
)
#: Bare call names that construct or invoke a model client.
MODEL_CALLS = {"OpenAI", "AzureOpenAI", "Anthropic", "ChatCompletion", "ChatOpenAI"}

# -- human_input ------------------------------------------------------------ #
#: Markers, in a string literal or a function name, of data a *person* produced.
#:
#: Deliberately **not** "annotation": in the testbed that word names the LLM's own output
#: (``annotations_<tag>_checkpoint.csv``), while the human-coded files are ``coding_*.csv``
#: and ``gold_human_*.csv``. A token that means "human" in one project and "model" in the
#: next is not evidence. These name a person's judgement in the coding/content-analysis
#: sense, which is the tradition the term comes from.
HUMAN_DATA_TOKENS = ("coding_", "coder", "codebook", "gold_human", "goldstandard",
                     "gold_standard", "human_label", "manual_", "adjudicat", "consensus",
                     "ground_truth")
#: Calls that pull records in from disk -- ``human_input`` refines ``@data_input``, so
#: something must actually be read.
DATA_LOAD_CALLS = {"read_csv", "read_excel", "read_json", "read_parquet", "read_text",
                   "load", "loads", "glob", "rglob", "iterdir", "open", "readlines"}

# -- external_tool ---------------------------------------------------------- #
#: The computation left the process. Matched against *dotted* calls, because ``run`` and
#: ``call`` as bare names are far too common to be evidence of anything. ``shutil.which``
#: counts: it is how code looks for a binary it is about to depend on.
SHELL_TOKENS = ("subprocess.", "os.system", "os.popen", "os.spawn", "os.exec",
                "shutil.which", "pexpect.", "plumbum.", "commands.getoutput")
#: Bare names that are unambiguous even without their module (``from subprocess import
#: Popen``). ``run`` and ``call`` are deliberately absent.
SHELL_CALLS = {"Popen", "check_output", "check_call", "getoutput", "getstatusoutput"}

# -- stochastic ------------------------------------------------------------- #
#: Calls that draw on a random source. ``Random`` catches ``random.Random(seed)``.
RNG_CALLS = {
    "random", "randint", "randrange", "choice", "choices", "shuffle", "sample",
    "uniform", "gauss", "normalvariate", "randn", "rand", "permutation",
    "default_rng", "seed", "Random", "getrandbits", "randbytes", "uuid4",
    "token_hex", "token_bytes", "train_test_split",
}
#: Parameter names that mean "the caller controls the randomness".
SEED_PARAMS = ("seed", "rng", "random_state", "generator")
#: Variable names that mean the RNG draw is a retry backoff, not a result.
JITTER_NAMES = ("wait", "backoff", "jitter", "delay", "sleep", "pause", "retry")

# -- statistical ------------------------------------------------------------ #
#: Statistics libraries: calling into one means a reported number is being computed.
STATS_TOKENS = ("scipy.stats", "statsmodels", "sklearn.metrics", "krippendorff",
                "pingouin", "numpy.corrcoef")
STATS_CALLS = {
    "cohen_kappa_score", "f1_score", "accuracy_score", "precision_score",
    "recall_score", "roc_auc_score", "confusion_matrix", "pearsonr", "spearmanr",
    "kendalltau", "ttest_ind", "ttest_rel", "chi2_contingency", "mannwhitneyu",
    "wilcoxon", "corrcoef", "bootstrap",
}
#: Function-name fragments that name a statistic. Weaker evidence than a library call.
STATS_NAME_HINTS = ("alpha", "kappa", "icr", "agreement", "reliability", "correlation",
                    "pvalue", "p_value", "ttest", "effect_size", "_stats", "significance")
#: Calls that aggregate many values into one -- the shape of computing a statistic.
AGGREGATE_CALLS = {"mean", "median", "sum", "count", "std", "var", "min", "max", "len",
                   "value_counts", "nunique", "describe", "agg", "corr", "mode", "quantile"}

# -- unit_of_analysis ------------------------------------------------------- #
#: Calls that drop or subset records -- the sample changes size here.
SUBSET_CALLS = {"drop", "dropna", "drop_duplicates", "query", "isin", "nlargest",
                "nsmallest", "head", "tail", "truncate", "filter", "sample"}
#: Function-name fragments that announce a selection step.
SUBSET_NAME_HINTS = ("filter", "select", "exclude", "subset", "narrow", "prune",
                     "restrict", "dedup", "sample", "shortlist")

# -- human_decision --------------------------------------------------------- #
#: Calls that hand the decision to a person.
HUMAN_CALLS = {"input", "confirm", "prompt", "getpass"}

# -- validation ------------------------------------------------------------- #
#: Function-name prefixes that announce a guard.
VALIDATION_PREFIXES = ("check_", "validate_", "verify_", "ensure_", "assert_", "is_valid")
