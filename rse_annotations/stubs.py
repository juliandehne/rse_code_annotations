"""Pattern-based ``pytest`` stub generation (no LLM, no network).

Each annotation kind has a *clear, fixed shape*, so a useful test scaffold can be
generated from pure introspection — no model required:

* ``@functional`` — pure maths: assert determinism now, plus a stub to pin the
  result against a known value (and the inferred formula as a comment to check by
  eye);
* ``@mapping`` — shape/format transform: build an input, assert the output shape;
* ``@data_input`` — reads a file/source: write a sample file into ``tmp_path``,
  call the function, assert the parsed result;
* ``@data_output`` — writes a file/sink: call the function against ``tmp_path``,
  assert the file exists and its contents.

Every generated body is scaffolding: ``# TODO`` markers and ``pytest.skip`` guard
the stubs so they never silently *pass* on fabricated expectations.
"""

from __future__ import annotations

import inspect
import keyword
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .formula import infer_formula
from .registry import AnnotationInfo


@dataclass
class StubFile:
    """A generated test module: where it goes and what it contains."""

    path: Path
    source_module: str
    content: str
    stub_count: int


def _safe_ident(name: str) -> str:
    """Turn an arbitrary module label into a valid python identifier fragment."""
    ident = re.sub(r"\W", "_", name).strip("_")
    if not ident or ident[0].isdigit():
        ident = "mod_" + ident
    if keyword.iskeyword(ident):
        ident += "_"
    return ident


def _signature(info: AnnotationInfo) -> str:
    try:
        return str(inspect.signature(info.func))
    except (TypeError, ValueError):
        return "(...)"


def _param_names(info: AnnotationInfo) -> List[str]:
    try:
        sig = inspect.signature(info.func)
    except (TypeError, ValueError):
        return []
    return [p.name for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]


def _fields_comment(info: AnnotationInfo) -> List[str]:
    if not info.fields:
        return []
    lines = ["    # Declared fields:"]
    for key, desc in info.fields.items():
        lines.append(f"    #   - {key}: {desc}")
    return lines


def _functional_stub(info: AnnotationInfo) -> str:
    name = info.name
    params = _param_names(info)
    call_args = ", ".join(params) if params else ""
    formula = infer_formula(info)
    formula_line = ""
    if formula.ast_forms:
        formula_line = f"    # Inferred formula: {formula.ast_forms[0]}\n"
    elif formula.sympy_form:
        formula_line = f"    # Inferred formula (SymPy): {formula.sympy_form}\n"
    arrange = "\n".join(f"    # {p} = ..." for p in params) or "    # (no parameters)"
    return (
        f"def test_{name}_is_deterministic():\n"
        f'    """@functional: pure and deterministic -- same inputs, same output."""\n'
        f"{formula_line}"
        f"{arrange}\n"
        f"    # args = ({call_args}{',' if len(params) == 1 else ''})\n"
        f"    # assert {name}(*args) == {name}(*args)\n"
        f'    pytest.skip("TODO: supply representative inputs and assert determinism")\n'
        f"\n\n"
        f"def test_{name}_matches_expected():\n"
        f'    """Pin the result against a KNOWN value (do not fabricate one)."""\n'
        f"    # expected = ...  # a value you have derived independently\n"
        f"    # assert {name}(...) == expected\n"
        f'    pytest.skip("TODO: assert against an independently known expected value")\n'
    )


def _mapping_stub(info: AnnotationInfo) -> str:
    name = info.name
    fields = "\n".join(_fields_comment(info))
    fields = (fields + "\n") if fields else ""
    return (
        f"def test_{name}_transforms_shape():\n"
        f'    """@mapping: transforms one in-memory shape/format into another."""\n'
        f"{fields}"
        f"    # sample_input = ...  # build a representative input object\n"
        f"    # result = {name}(sample_input)\n"
        f"    # assert ...  # check the output shape / representative values\n"
        f'    pytest.skip("TODO: build an input and assert the transformed output")\n'
    )


def _data_input_stub(info: AnnotationInfo) -> str:
    name = info.name
    fields = "\n".join(_fields_comment(info))
    fields = (fields + "\n") if fields else ""
    return (
        f"def test_{name}_reads_source(tmp_path):\n"
        f'    """@data_input: reads data from a file/source into memory."""\n'
        f"{fields}"
        f"    # sample = tmp_path / \"input.csv\"\n"
        f"    # sample.write_text(\"...\")  # a minimal file in the expected format\n"
        f"    # result = {name}(str(sample))\n"
        f"    # assert ...  # the parsed records match what you wrote\n"
        f'    pytest.skip("TODO: write a sample source file and assert the parse")\n'
    )


def _data_output_stub(info: AnnotationInfo) -> str:
    name = info.name
    fields = "\n".join(_fields_comment(info))
    fields = (fields + "\n") if fields else ""
    return (
        f"def test_{name}_writes_sink(tmp_path):\n"
        f'    """@data_output: writes in-memory data out to a file/sink."""\n'
        f"{fields}"
        f"    # out = tmp_path / \"output.csv\"\n"
        f"    # {name}(..., str(out))  # direct the write into tmp_path\n"
        f"    # assert out.exists()\n"
        f"    # assert out.read_text() == ...  # expected contents\n"
        f'    pytest.skip("TODO: invoke the writer and assert the produced file")\n'
    )


_STUB_BY_KIND = {
    "functional": _functional_stub,
    "mapping": _mapping_stub,
    "data_input": _data_input_stub,
    "data_output": _data_output_stub,
}


def stub_for(info: AnnotationInfo) -> str:
    """Return the pytest stub body for a single annotation."""
    header = (f"# --- @{info.kind} {info.name}{_signature(info)}  "
              f"({info.location}) ---\n")
    builder = _STUB_BY_KIND.get(info.kind, _mapping_stub)
    return header + builder(info)


def _module_import_line(module: str, names: List[str]) -> str:
    if module in ("<unknown>", "", "__main__") or "." in module and module.startswith("<"):
        return f"# NOTE: could not resolve an import for module {module!r}\n"
    joined = ", ".join(sorted(set(names)))
    return f"from {module} import {joined}  # noqa: F401  (imported for the stubs below)\n"


def generate_stub_module(module: str, infos: List[AnnotationInfo]) -> str:
    """Render a full pytest module for all annotations from one source module."""
    names = [i.name for i in infos]
    lines = [
        f'"""Auto-generated pytest stubs for {module}.',
        "",
        "Generated by rse_code_annotations (pattern-based, no LLM). Every test is a",
        "SKIPPED scaffold: fill in the TODOs with real inputs and independently known",
        "expected values -- the generator never fabricates expectations.",
        '"""',
        "",
        "import pytest",
        "",
        _module_import_line(module, names).rstrip("\n"),
        "",
        "",
    ]
    body = "\n\n".join(stub_for(i) for i in infos)
    return "\n".join(lines) + body + "\n"


def generate_stub_files(infos: List[AnnotationInfo], out_dir) -> List[StubFile]:
    """Group annotations by source module and render one stub file per module.

    Args:
        infos: annotations to scaffold (any mix of kinds).
        out_dir: directory to write ``test_<module>.py`` files into.

    Returns:
        One :class:`StubFile` per source module (nothing is written to disk here;
        the caller decides when to write, so the flow can preview first).
    """
    out_dir = Path(out_dir)
    by_module: Dict[str, List[AnnotationInfo]] = {}
    for info in infos:
        by_module.setdefault(info.module, []).append(info)

    files: List[StubFile] = []
    for module, module_infos in by_module.items():
        fname = f"test_{_safe_ident(module.rsplit('.', 1)[-1])}.py"
        files.append(StubFile(
            path=out_dir / fname,
            source_module=module,
            content=generate_stub_module(module, module_infos),
            stub_count=len(module_infos),
        ))
    return files
