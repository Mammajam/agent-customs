"""customs command line.

    customs check "pip install reqeusts"   # human-readable verdict
    customs hook                            # Claude Code PreToolUse hook (stdin/stdout)
"""

from __future__ import annotations

import argparse
import sys

from customs.checkpoint import check_command, overall
from customs.hook import run as run_hook
from customs.verdict import Verdict


def _check(command: str) -> int:
    decisions = check_command(command)
    if not decisions:
        print("No installs, clones or skill fetches found.")
        return 0
    for d in decisions:
        print(f"{d.verdict.value.upper():8} {d.declaration.ecosystem.value:6} {d.declaration.name}")
        for reason in d.reasons:
            print(f"         - {reason}")
        if d.suggestion:
            print(f"         did you mean: {d.suggestion}")
    verdict = overall(decisions)
    print(f"\nOverall: {verdict.value.upper()}")
    return 1 if verdict is Verdict.BLOCK else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="customs")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="check a shell command")
    check.add_argument("command")
    sub.add_parser("hook", help="run as a Claude Code PreToolUse hook")
    args = parser.parse_args(argv)
    if args.cmd == "check":
        return _check(args.command)
    return run_hook(sys.stdin, sys.stdout)


if __name__ == "__main__":
    sys.exit(main())
