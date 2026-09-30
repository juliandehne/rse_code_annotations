"""Test generation (pattern-based pytest scaffolds) and differential verification."""

from .generators import DifferentialVerifier, TestGenerator
from .stubs import StubFile, generate_stub_files, generate_stub_module, stub_for
from .verify import DiffResult, differential_check

__all__ = ["TestGenerator", "DifferentialVerifier", "StubFile", "generate_stub_files",
           "generate_stub_module", "stub_for", "DiffResult", "differential_check"]
