"""@validation: a guard asserting a property of the data."""
import ast

from .._base import Concern

PREFIXES = ("check_", "validate_", "verify_", "ensure_", "assert_", "is_valid")


class Validation(Concern):
    assertion = "This guard is actually called somewhere in the pipeline."

    def detect(self, v):
        if not v.name.startswith(PREFIXES):
            return None
        if any(isinstance(n, (ast.Raise, ast.Assert)) for n in ast.walk(v.node)):
            return "guards a data invariant (raises/asserts)", "high"
        return "named like a guard", "medium"


CONCERN = Validation("validation")
