"""Run rse_annotations against the testbed: lni_study on its decorated branch.

The branch ``feat/rse-code-annotations`` of lni_study marks real pipeline functions
(``@functional``, ``@mapping``, ``@data_input``, ``@data_output``). This script clones it
into a temp directory, runs the analysis (and with ``--inspect`` the review), checks
that the marked functions were found, and deletes the clone unless ``--keep`` is given.

    python testbed/run_testbed.py                       # clone from GitHub
    python testbed/run_testbed.py --repo ../lni_study   # clone from a local checkout
    python testbed/run_testbed.py --inspect --keep      # review, keep inspection.yaml
"""
import argparse
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from rse_annotations.__main__ import main as run
from rse_annotations.analysis import scan

REPO = "git@github.com:juliandehne/lni_study.git"
BRANCH = "feat/rse-code-annotations"
MIN_MARKED = 6


def _force_remove(func, path, _):
    Path(path).chmod(stat.S_IWRITE)  # git objects are read-only on Windows
    func(path)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", default=REPO, help="git URL or local path of lni_study")
    p.add_argument("--branch", default=BRANCH)
    p.add_argument("--inspect", action="store_true", help="also review the marked functions")
    p.add_argument("--keep", action="store_true", help="keep the clone")
    args = p.parse_args(argv)

    tmp = Path(tempfile.mkdtemp(prefix="rse_testbed_"))
    try:
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", args.branch,
                        str(args.repo), str(tmp / "lni_study")], check=True)
        src = tmp / "lni_study" / "src"
        run([str(src)])
        if args.inspect:
            run([str(src), "--inspect"])
        marked = [r.qualname for r in scan(src)[0] if r.marked]
        ok = len(marked) >= MIN_MARKED
        print(f"\ntestbed: {len(marked)} marked functions found "
              f"({'ok' if ok else f'expected at least {MIN_MARKED}'})")
        return 0 if ok else 1
    finally:
        if args.keep:
            print(f"clone kept at {tmp}")
        else:
            shutil.rmtree(tmp, onerror=_force_remove)


if __name__ == "__main__":
    sys.exit(main())
