"""@unit_of_analysis: changes which units (records, papers, participants) are in the sample."""
import ast

from .._base import Concern

CALLS = {"drop", "dropna", "drop_duplicates", "query", "isin", "nlargest", "nsmallest",
         "head", "tail", "truncate", "filter", "sample"}
NAME_HINTS = ("filter", "select", "exclude", "subset", "narrow", "prune", "restrict",
              "dedup", "sample", "shortlist")


class UnitOfAnalysis(Concern):
    assertion = "Every dropped record has a documented reason."

    def detect(self, v):
        hits = sorted(v.called & CALLS)
        if hits:
            named = any(t in v.name for t in NAME_HINTS)
            return f"drops or subsets records ({', '.join(hits[:3])})", "high" if named else "medium"
        if (v.returns and not v.does_io
                and any(isinstance(n, ast.comprehension) and n.ifs for n in ast.walk(v.node))):
            return "filters in a comprehension: may change the sample size", "low"
        return None
