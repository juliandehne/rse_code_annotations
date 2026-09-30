#!/usr/bin/env python3
"""End-to-end demo: run every rse_code_annotations feature against a real testbed.

The testbed is the ``lni_study`` repo, which carries the four role annotations
(``@functional`` / ``@mapping`` / ``@data_input`` / ``@data_output``) on
``src/compute_icr.py`` and ``src/krippendorff_reference.py``. This script clones it
into a throwaway directory, drives the documented CLI against it, asserts that each
feature actually produced what it promises, and then deletes everything it created.

Run it::

    python scripts/demo_lni_testbed.py            # clone from GitHub, demo, clean up
    python scripts/demo_lni_testbed.py --keep     # leave the clone for inspection
    python scripts/demo_lni_testbed.py --repo /path/to/local/lni_study   # offline

What it demonstrates, in order:

    1. discovery         -- the tool finds the 6 annotations across the tree
    2. Option 3 coverage -- static AST scan -> annotation_coverage.md   (never imports)
    3. Option 2 stubs    -- pattern-based pytest scaffolds -> tests/
    4. pytest            -- the generated stubs collect and SKIP (nothing silently passes)
    5. Option 1 inspect  -- @functional review, verdicts -> inspection.yaml

Nothing is installed and nothing outside the temp directory is written: the package is
made importable via PYTHONPATH, so this exercises the *working copy* of
``rse_code_annotations`` (including uncommitted changes), not an installed release.

Exit code is 0 only if every step passed.
"""

from __future__ import annotations

import argparse
import atexit
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

# The annotations live on this branch, NOT on main. Cloning main yields a tree with
# zero annotations and the demo would be vacuous, so pin it explicitly.
DEFAULT_REPO = "git@github.com:juliandehne/lni_study.git"
DEFAULT_BRANCH = "feat/rse-code-annotations"

# rse_code_annotations repo root (this file lives in <root>/scripts/).
PKG_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_ANNOTATIONS = 6  # 1 functional, 3 mapping, 1 data_input, 1 data_output


# --------------------------------------------------------------------------------
# pretty output
# --------------------------------------------------------------------------------

class Reporter:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def step(self, n: int, title: str) -> None:
        print()
        print("=" * 78)
        print(f"  STEP {n}  {title}")
        print("=" * 78)

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {label}" + (f"  --  {detail}" if detail else ""))
        if not ok:
            self.failures.append(label)
        return ok


# --------------------------------------------------------------------------------
# teardown -- must survive exceptions, Ctrl-C, and Windows read-only .git objects
# --------------------------------------------------------------------------------

def _force_remove(func, path, _exc):
    """rmtree onexc handler: git marks .git/objects read-only on Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def destroy(tmp: Path, keep: bool = False) -> None:
    """Remove everything the run created. Safe to call twice (atexit + finally)."""
    if keep:
        if tmp.exists():
            print(f"\n[teardown] --keep given; leaving {tmp}")
        return
    if not tmp.exists():
        return
    # Guard: only ever delete inside the system temp dir. A bug in path handling must
    # never let this loose on the user's real working copy.
    root = Path(tempfile.gettempdir()).resolve()
    target = tmp.resolve()
    if root not in target.parents:
        print(f"\n[teardown] REFUSING to delete {target}: outside {root}")
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(target, onexc=_force_remove)
    else:  # pragma: no cover - older interpreters
        shutil.rmtree(target, onerror=lambda f, p, e: _force_remove(f, p, e))
    print(f"\n[teardown] removed {target}")


# --------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------

def run_cli(clone: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    """Invoke the documented CLI against the clone, with the working copy on PYTHONPATH."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "rse_annotations", str(clone), *args],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env, cwd=str(PKG_ROOT), timeout=300,
    )


def tail(text: str, n: int = 12) -> str:
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return "\n".join("      | " + ln for ln in lines[-n:])


# --------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=DEFAULT_REPO,
                    help=f"clone source: URL or local path (default: {DEFAULT_REPO})")
    ap.add_argument("--branch", default=DEFAULT_BRANCH,
                    help=f"branch carrying the annotations (default: {DEFAULT_BRANCH})")
    ap.add_argument("--keep", action="store_true",
                    help="do not delete the clone at the end (for debugging)")
    args = ap.parse_args()

    r = Reporter()
    # .resolve() matters: on Windows mkdtemp can hand back an 8.3 short path
    # (C:\Users\JULIAN~1.DEH\...) while the CLI prints the long form, and then any
    # path comparison against its output silently fails to match.
    tmp = Path(tempfile.mkdtemp(prefix="rse_annots_demo_")).resolve()
    # Belt and braces: if we die anywhere below -- exception, Ctrl-C, sys.exit --
    # the clone still gets removed.
    atexit.register(destroy, tmp, args.keep)

    print(f"[setup] temp dir : {tmp}")
    print(f"[setup] package  : {PKG_ROOT}  (via PYTHONPATH, not installed)")
    print(f"[setup] testbed  : {args.repo} @ {args.branch}")

    try:
        clone = tmp / "lni_study"

        # ---- STEP 0: clone the testbed --------------------------------------
        r.step(0, "Setup: clone the lni_study testbed")
        cp = subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1",
             "--branch", args.branch, args.repo, str(clone)],
            capture_output=True, text=True, timeout=300,
        )
        if not r.check(cp.returncode == 0, "git clone succeeded",
                       f"{args.branch}"):
            print(tail(cp.stderr))
            return 1
        head = subprocess.run(["git", "-C", str(clone), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        r.check((clone / "src" / "compute_icr.py").is_file(),
                "testbed has the annotated sources", f"HEAD={head}")

        # ---- STEP 1: discovery ----------------------------------------------
        # No mode flag + no TTY: the menu hits EOF and quits, but the header still
        # prints the discovery summary, which is what we assert on.
        r.step(1, "Discovery: find the annotations in the tree")
        cp = run_cli(clone, stdin="")
        found = f"Found {EXPECTED_ANNOTATIONS} annotation(s)"
        ok = r.check(found in cp.stdout, f"discovered {EXPECTED_ANNOTATIONS} annotations")
        for kind in ("functional", "mapping", "data_input", "data_output"):
            r.check(f"@{kind}" in cp.stdout, f"  kind present: @{kind}")
        if not ok:
            print(tail(cp.stdout))
            print(tail(cp.stderr))

        # ---- STEP 2: Option 3 -- coverage (static, never imports) -------------
        r.step(2, "Option 3: annotation coverage + candidates (static AST scan)")
        cp = run_cli(clone, "--coverage")
        report = clone / "annotation_coverage.md"
        r.check(cp.returncode == 0, "--coverage exited 0")
        r.check(report.is_file(), "wrote annotation_coverage.md",
                f"{report.stat().st_size} bytes" if report.is_file() else "MISSING")
        if report.is_file():
            body = report.read_text(encoding="utf-8", errors="replace")
            r.check("files scanned" in body, "  report contains a scan summary")
            r.check(len(body.splitlines()) > 20, "  report lists candidates",
                    f"{len(body.splitlines())} lines")
        print(tail(cp.stdout, 8))

        # ---- STEP 3: Option 2 -- generate pytest stubs ------------------------
        # The testbed already ships a handwritten tests/test_short_paper_cap.py, so
        # globbing tests/ would miscredit it to the generator. Assert on the files the
        # CLI actually reports writing instead.
        r.step(3, "Option 2: generate pytest stubs for every annotation")
        tests_dir = clone / "tests"
        before = set(tests_dir.glob("test_*.py")) if tests_dir.is_dir() else set()
        cp = run_cli(clone, "--stubs")
        r.check(cp.returncode == 0, "--stubs exited 0")

        written = [Path(ln.split("wrote ", 1)[1].split("  (")[0])
                   for ln in cp.stdout.splitlines() if ln.strip().startswith("wrote ")]
        r.check(len(written) == 2, "generated a stub file per annotated module",
                ", ".join(p.name for p in written) or "NONE")
        r.check(all(p.is_file() for p in written), "  the reported files exist on disk")
        r.check(f"Generated {EXPECTED_ANNOTATIONS} stub(s)" in cp.stdout,
                f"  one stub per annotation ({EXPECTED_ANNOTATIONS})")
        if written:
            joined = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in written)
            r.check("pytest.skip" in joined,
                    "  every stub is a SKIP scaffold (nothing silently passes)")
            r.check("TODO" in joined, "  every stub carries a TODO, not a fake expectation")
        # Regeneration overwrites previously generated stubs of the same name; it must
        # not clobber handwritten tests sitting alongside them.
        handwritten = before - set(written)
        if handwritten:
            r.check(all(p.is_file() for p in handwritten),
                    "  handwritten tests left intact",
                    ", ".join(p.name for p in sorted(handwritten)))
        print(tail(cp.stdout, 8))

        # ---- STEP 4: the generated stubs actually collect ---------------------
        r.step(4, "pytest: the generated stubs collect and skip")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PKG_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        cp = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "-q", "--no-header"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, cwd=str(clone), timeout=300,
        )
        out = cp.stdout + cp.stderr
        # Stubs are skips, so pytest exits 0 with "N skipped" and zero collection errors.
        r.check("error" not in out.lower() or "0 error" in out.lower(),
                "no collection errors")
        r.check("skipped" in out, "stubs collected and skipped",
                next((ln.strip() for ln in out.splitlines()
                      if "skipped" in ln), "?"))
        print(tail(out, 6))

        # ---- STEP 5: Option 1 -- inspect @functional --------------------------
        # The prompt is "[y]es / [n]o / [s]kip"; feed enough answers for every
        # @functional. Extra lines are harmless, EOF falls back to the default.
        r.step(5, "Option 1: inspect @functional and record verdicts")
        cp = run_cli(clone, "--inspect", stdin="y\n" * 10)
        verdicts = clone / "inspection.yaml"
        r.check(cp.returncode == 0, "--inspect exited 0")
        r.check(verdicts.is_file(), "wrote inspection.yaml")
        if verdicts.is_file():
            body = verdicts.read_text(encoding="utf-8", errors="replace")
            r.check("accepted" in body, "  verdict recorded as accepted")
        print(tail(cp.stdout, 8))

        # ---- summary ----------------------------------------------------------
        print()
        print("=" * 78)
        if r.failures:
            print(f"  RESULT: {len(r.failures)} CHECK(S) FAILED")
            for f in r.failures:
                print(f"    - {f}")
            print("=" * 78)
            return 1
        print("  RESULT: ALL CHECKS PASSED -- every feature demonstrated end-to-end")
        print("=" * 78)
        return 0

    finally:
        # Primary teardown. atexit is only the safety net for a hard exit.
        destroy(tmp, args.keep)
        atexit.unregister(destroy)


if __name__ == "__main__":
    sys.exit(main())
