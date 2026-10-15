"""@external_tool: the computation leaves the process (subprocess/shell)."""
import ast

from .._base import Concern

TOKENS = ("subprocess.", "os.system", "os.popen", "os.spawn", "os.exec",
          "shutil.which", "pexpect.", "plumbum.")
CALLS = {"Popen", "check_output", "check_call", "getoutput", "getstatusoutput"}


def detect(v):
    hits = v.hits(TOKENS, CALLS)
    if not hits:
        return None
    shell = any(isinstance(n, ast.keyword) and n.arg == "shell"
                and getattr(n.value, "value", None) is True for n in ast.walk(v.node))
    return f"shells out ({', '.join(hits[:2])}){' with shell=True' if shell else ''}", "high"


CONCERN = Concern(
    "external_tool",
    "The tool and its version are part of the method: are they recorded, and does a missing binary fail loudly?",
    detect)
