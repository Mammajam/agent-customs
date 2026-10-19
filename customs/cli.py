"""customs command line.

    customs check "pip install reqeusts"   # human-readable verdict
    customs hook                            # Claude Code PreToolUse hook (stdin/stdout)
    customs fix requirements.txt --test "python3 -m pytest -q"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from customs import allowlist
from customs.checkpoint import check_command, overall
from customs.hook import run as run_hook
from customs.remediate import apply_fix
from customs.verdict import Verdict


def _check(command: str) -> int:
    decisions = check_command(command, allow=allowlist.load())
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


def manifest_installs(path: Path) -> str:
    """One install command covering every dependency in the manifest."""
    if path.name == "package.json":
        doc = json.loads(path.read_text())
        names = [*doc.get("dependencies", {}), *doc.get("devDependencies", {})]
        return " && ".join(f"npm install {n}" for n in names) or "true"
    lines = [line.strip() for line in path.read_text().splitlines()]
    reqs = [line for line in lines if line and not line.startswith("#")]
    return " && ".join(f"pip install {r}" for r in reqs) or "true"


def _fix(args) -> int:
    install = args.install or manifest_installs(args.manifest)
    decisions = check_command(install, allow=allowlist.load())
    result = apply_fix(args.manifest, decisions, args.test)
    print(f"Status: {result.status}")
    for bad, good in result.replacements.items():
        print(f"  {bad} -> {good}")
    for note in result.notes:
        print(f"  note: {note}")
    if result.status == "tests-failed":
        print(result.test_output)
    return 0 if result.status in ("fixed", "nothing to fix") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="customs")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="check a shell command")
    check.add_argument("command")
    sub.add_parser("hook", help="run as a Claude Code PreToolUse hook")
    fix = sub.add_parser("fix", help="replace blocked names in a manifest and prove it with tests")
    fix.add_argument("manifest", type=Path)
    fix.add_argument("--test", required=True, help="command that must pass after the patch")
    fix.add_argument("--install", help="install line to check, for example 'pip install reqeusts'")
    args = parser.parse_args(argv)
    if args.cmd == "check":
        return _check(args.command)
    if args.cmd == "fix":
        return _fix(args)
    return run_hook(sys.stdin, sys.stdout)


if __name__ == "__main__":
    sys.exit(main())
