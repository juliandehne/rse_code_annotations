"""Runner: ``python -m rse_annotations PATH [--analyze | --inspect] [--json] [--concern NAME]``."""
import argparse
import sys

from .analysis import scan, to_json, to_text
from .decorators import CONCERNS
from .inspection import review


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="rse-annotations", description=__doc__)
    p.add_argument("path", help="directory or .py file to scan (never imported)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--analyze", action="store_true", help="coverage report (default)")
    mode.add_argument("--inspect", action="store_true", help="review marked functions y/n/s")
    p.add_argument("--json", action="store_true", help="analysis as JSON")
    p.add_argument("--concern", choices=list(CONCERNS), help="inspect only this concern")
    args = p.parse_args(argv)
    if args.inspect:
        review(args.path, args.concern)
    else:
        records, errors = scan(args.path)
        print(to_json(records, errors) if args.json else to_text(records, errors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
