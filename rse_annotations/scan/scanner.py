"""Static (AST) decorator coverage: what is decorated, and what should be.

The inspection plugin works by *reflection*: the decorators
register themselves at import time, so it can only ever see functions that are
**already decorated**, in modules that **import cleanly**. Coverage is the opposite
question -- *which functions are missing a decorator?* -- so it cannot use the
registry at all:

* an undecorated function never enters the registry, by construction; and
* research code frequently refuses to import (a missing optional dependency, a
  module that calls ``sys.exit()`` at the bottom, an API key read at import time).

So this module never imports the target. It parses every ``*.py`` file under the
root with :mod:`ast`, walks the module/class/function structure, and reports:

1. **coverage** -- every function and method found, whether it carries one of the
   decorators, aggregated per concern and per file; and
2. **candidates** -- for each *undecorated* function, the decorator it most likely
   deserves, inferred from the same syntactic heuristics the placement checks use
   (:mod:`rse_annotations.scan.ast_utils`): a file write implies ``@data_output``, a file
   read implies ``@data_input``, pure arithmetic implies ``@functional``, and an
   argument-in/value-out transform implies ``@mapping``; and
3. **audit hazards** -- a second, *orthogonal* axis (see ``PROPOSED_ANNOTATIONS.md``).
   The dataflow decorators answer *where does data flow?*. They cannot express *"this
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

import ast
from pathlib import Path
from typing import List, Optional, Tuple

from ..decorators.discovery import _iter_python_files, _module_name_for
from .ast_utils import (_alias_map, _decorator_concern, _called_names, _file_io_calls,
                        _param_names, _returns_a_value)
from . import vocabulary as vocab
from .candidates import _suggest
from .hazards import _flag_uncalled_validations, _hazards, _propagate_hazards
from .model import CoverageReport, FunctionRecord

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
            concern = _decorator_concern(node, aliases)
            if concern is None and eligible:
                suggested, reason, confidence = _suggest(node)
            else:
                suggested, reason, confidence = None, "", ""
            # Hazards are orthogonal to the dataflow role, so they are computed for
            # *decorated* functions too -- `compute_dimension_icr` is a @mapping and a
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
                concern=concern,
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
    return (path.name in vocab.SKIP_FILE_NAMES
            or path.name.startswith(vocab.SKIP_FILE_PREFIXES))


def scan_path(root) -> CoverageReport:
    """Statically scan ``root`` and report decorator coverage plus candidates.

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
