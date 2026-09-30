"""Infer the mathematical formula a ``@functional`` implements, for human inspection.

Recovering "the formula" from arbitrary code is undecidable in general (it subsumes
the halting problem). But for the tractable case — a *pure, scalar, arithmetic*
function — several practical techniques exist, and this module runs the ones that
apply and prints their output so a human can eyeball correctness. It never claims a
function is *correct*; it only surfaces what the code computes.

Backends (each best-effort, independently optional):

1. **AST rendering** (always available, no dependencies) — walk the function's
   syntax tree and pretty-print its ``return`` expression(s) as infix mathematics.
   Pure syntax, no execution: safe on any code, but only as faithful as the source
   (it shows the expression, it does not simplify it).

2. **SymPy symbolic execution** (optional, ``pip install sympy``) — call the function
   with SymPy symbols in place of its scalar parameters. Python's operator overloading
   makes the function *build a symbolic expression* instead of a number; SymPy then
   simplifies it to a closed form and can emit LaTeX. Works only when the body is
   scalar arithmetic that tolerates symbolic inputs (no branching on values, no
   arrays, no library calls) — otherwise it raises and we report that.

3. **latexify** (optional, ``pip install latexify-py``) — a dedicated AST→LaTeX
   converter for Python functions; complements (1) with publication-quality output.

For code the symbolic backends cannot handle (loops over matrices, library calls
like Krippendorff's alpha), formula inference does not apply — reach for the
differential-testing harness (``differential_check``) to pin correctness against a
trusted reference instead.

On the wider landscape (documented in FORMULA_INFERENCE.md): formal-methods tools
(Dafny, Why3, Coq/Isabelle, KeY) *verify code against a specification you write* —
they cannot infer the intended formula from code alone. So for "print the formula for
human inspection" the AST/SymPy/latexify route is the right tool; formal verifiers are
the complementary next step once a human has confirmed the formula.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from typing import List, Optional

from ..decorators.registry import DecoratorInfo


@dataclass
class FormulaResult:
    """Formulas inferred for one function by the available backends."""

    name: str
    location: str
    ast_forms: List[str] = field(default_factory=list)
    sympy_form: Optional[str] = None
    sympy_latex: Optional[str] = None
    latexify_form: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    @property
    def any_formula(self) -> bool:
        return bool(self.ast_forms or self.sympy_form or self.latexify_form)


# --------------------------------------------------------------------------- #
# Backend 1: AST rendering (dependency-free)
# --------------------------------------------------------------------------- #

_BINOP = {
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
    ast.Pow: "**", ast.Mod: "%", ast.FloorDiv: "//",
}
_CMP = {
    ast.Eq: "=", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
    ast.Gt: ">", ast.GtE: ">=",
}


def _render(node: ast.AST) -> str:
    """Render an expression node as an infix math string (best-effort)."""
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOP:
        return f"({_render(node.left)} {_BINOP[type(node.op)]} {_render(node.right)})"
    if isinstance(node, ast.UnaryOp):
        op = {ast.USub: "-", ast.UAdd: "+"}.get(type(node.op), "?")
        return f"{op}{_render(node.operand)}"
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP:
        return f"({_render(node.left)} {_CMP[type(node.ops[0])]} {_render(node.comparators[0])})"
    if isinstance(node, ast.Call):
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "f")
        args = ", ".join(_render(a) for a in node.args)
        return f"{name}({args})"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return f"{_render(node.value)}[...]"
    if isinstance(node, (ast.Tuple, ast.List)):
        return "[" + ", ".join(_render(e) for e in node.elts) + "]"
    # Fallback: unparse if available (py3.9+).
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return "<expr>"


def _ast_formulas(info: DecoratorInfo) -> List[str]:
    try:
        import textwrap
        src = textwrap.dedent(inspect.getsource(info.func))
        tree = ast.parse(src)
    except (OSError, TypeError, SyntaxError):
        return []
    func = next((n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
    if func is None:
        return []
    forms = []
    for n in ast.walk(func):
        if isinstance(n, ast.Return) and n.value is not None:
            forms.append(f"{info.name}(...) = {_render(n.value)}")
    return forms


# --------------------------------------------------------------------------- #
# Backend 2: SymPy symbolic execution
# --------------------------------------------------------------------------- #

def _sympy_formula(info: DecoratorInfo) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (pretty, latex, note). Only works for scalar-arithmetic functions."""
    try:
        import sympy
    except ImportError:
        return None, None, "sympy not installed (pip install sympy) — skipped"

    try:
        sig = inspect.signature(info.func)
    except (TypeError, ValueError):
        return None, None, "no introspectable signature — skipped"

    params = [p for p in sig.parameters.values()
              if p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY)]
    if not params:
        return None, None, "no positional parameters to symbolise — skipped"

    symbols = {p.name: sympy.Symbol(p.name, real=True) for p in params}
    try:
        result = info.func(**symbols)
        expr = sympy.simplify(result)
        return str(expr), sympy.latex(expr), None
    except Exception as exc:  # noqa: BLE001
        return None, None, (f"symbolic execution not applicable "
                            f"(needs pure scalar arithmetic): {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------- #
# Backend 3: latexify
# --------------------------------------------------------------------------- #

def _latexify_formula(info: DecoratorInfo) -> tuple[Optional[str], Optional[str]]:
    try:
        import latexify
    except ImportError:
        return None, "latexify not installed (pip install latexify-py) — skipped"
    try:
        return str(latexify.get_latex(info.func)), None
    except Exception as exc:  # noqa: BLE001
        return None, f"latexify could not convert: {type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def infer_formula(info: DecoratorInfo) -> FormulaResult:
    """Run every applicable backend and collect the inferred formulas."""
    res = FormulaResult(name=info.name, location=info.location)

    res.ast_forms = _ast_formulas(info)
    if not res.ast_forms:
        res.notes.append("AST: no explicit return expression found to render")

    pretty, latex, note = _sympy_formula(info)
    res.sympy_form, res.sympy_latex = pretty, latex
    if note:
        res.notes.append(f"SymPy: {note}")

    latex_form, lnote = _latexify_formula(info)
    res.latexify_form = latex_form
    if lnote:
        res.notes.append(f"latexify: {lnote}")

    return res


def render_formula(res: FormulaResult) -> str:
    """Human-readable block for one function's inferred formula(s)."""
    lines = [f"formula for {res.name}  ({res.location})"]
    for f in res.ast_forms:
        lines.append(f"  [AST]      {f}")
    if res.sympy_form:
        lines.append(f"  [SymPy]    {res.sympy_form}")
        lines.append(f"  [SymPy/TeX] {res.sympy_latex}")
    if res.latexify_form:
        lines.append(f"  [latexify] {res.latexify_form}")
    for n in res.notes:
        lines.append(f"  - {n}")
    return "\n".join(lines)
