"""@statistical: computes a number the paper reports."""
import ast

from .._base import Concern

TOKENS = ("scipy.stats", "statsmodels", "sklearn.metrics", "krippendorff", "pingouin",
          "numpy.corrcoef")
CALLS = {"cohen_kappa_score", "f1_score", "accuracy_score", "precision_score",
         "recall_score", "roc_auc_score", "confusion_matrix", "pearsonr", "spearmanr",
         "kendalltau", "ttest_ind", "ttest_rel", "chi2_contingency", "mannwhitneyu",
         "wilcoxon", "corrcoef", "bootstrap"}
NAME_HINTS = ("alpha", "kappa", "icr", "agreement", "reliability", "correlation",
              "pvalue", "p_value", "ttest", "effect_size", "_stats", "significance")
AGGREGATES = {"mean", "median", "sum", "count", "std", "var", "min", "max", "len",
              "value_counts", "nunique", "describe", "agg", "corr", "mode", "quantile"}
ARITH = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Pow, ast.Mod)


def detect(v):
    hits = v.hits(TOKENS, CALLS)
    if hits:
        return f"computes a statistic via {', '.join(hits[:2])}", "high"
    computes = v.called & AGGREGATES or any(
        isinstance(n, (ast.BinOp, ast.AugAssign)) and isinstance(n.op, ARITH)
        for n in ast.walk(v.node))
    if any(t in v.name for t in NAME_HINTS) and v.returns and not v.does_io and computes:
        return "name suggests a reported statistic", "medium"
    return None


CONCERN = Concern(
    "statistical",
    "Is this statistic pinned against a reference implementation or its cited definition?",
    detect, critical=True)
