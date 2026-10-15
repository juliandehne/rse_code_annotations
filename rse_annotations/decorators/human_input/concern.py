"""@human_input: an answer entered the study from a person (coding, annotation, gold standard)."""
import ast

from .._base import Concern

TOKENS = ("coding_", "coder", "codebook", "gold_human", "goldstandard", "gold_standard",
          "human_label", "manual_", "adjudicat", "consensus", "ground_truth")
LOAD_CALLS = {"read_csv", "read_excel", "read_json", "read_parquet", "read_text",
              "load", "loads", "glob", "rglob", "iterdir", "open", "readlines"}


class HumanInput(Concern):
    def detect(self, v):
        # file-name-like literals only: a sentence that mentions the gold standard is not evidence
        files = sorted({n.value for n in ast.walk(v.node)
                        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value
                        and not any(c.isspace() for c in n.value)
                        and any(t in n.value.lower() for t in TOKENS)})
        named = any(t.strip("_") in v.name for t in TOKENS)
        if not (files or named) or not (v.reads or v.called & LOAD_CALLS):
            return None
        if files:
            return f"reads human-coded data ({', '.join(files[:2])})", "high"
        return "named for human-coded data and reads a source", "medium"


CONCERN = HumanInput(
    "human_input",
    "Data was produced by people: are coders, codebook version and inter-coder reliability recorded?")
