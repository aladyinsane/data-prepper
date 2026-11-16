"""Command line: run and selftest. Exit codes: 0 ok, 1 an error check failed, 2 bad config or arguments."""

import argparse
import sys

from .config import ConfigError
from . import run as run_mod


def build_parser():
    p = argparse.ArgumentParser(prog="python -m data_prepper")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run a dataset through every stage")
    r.add_argument("dataset_folder", help="folder holding dataset.json")
    r.add_argument("--data-root", help="folder that relative source paths are resolved against (default: the dataset folder)")
    r.add_argument("--runs", default="runs", help="folder for run output (default: runs/ in the current folder)")
    sub.add_parser("selftest", help="run a small made-up dataset through every stage")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)  # a bad argument exits 2 by itself
    if args.command == "selftest":
        from . import selftest

        return selftest.main()
    try:
        code, run = run_mod.execute(args.dataset_folder, args.data_root, args.runs)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if run is not None:
        print(f"run folder: {run.dir}")
    return code
