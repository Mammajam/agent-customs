"""Claude Code PreToolUse hook.

Claude Code sends the pending tool call as JSON on stdin. For Bash calls the
command is checked; for a BLOCK the hook answers deny with the reason and a
suggested real name, for an INSPECT it answers ask, and otherwise it stays
silent so the call proceeds.

Any unexpected error answers ask, so a broken checkpoint never passes silently.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from customs.checkpoint import check_command, overall
from customs.verdict import Verdict


def _reason_text(decisions) -> str:
    lines = []
    for d in decisions:
        if d.verdict is Verdict.CLEAR:
            continue
        head = f"[{d.verdict.value.upper()}] {d.declaration.name}"
        lines.append(head + ": " + "; ".join(d.reasons))
        if d.suggestion:
            lines.append(f"  Did you mean `{d.suggestion}`?")
    return "\n".join(lines)


def _output(decision: str, reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def handle(payload: dict, registry=None) -> dict[str, Any] | None:
    if payload.get("tool_name") != "Bash":
        return None
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        return None

    decisions = check_command(command, registry)
    verdict = overall(decisions)
    if verdict is Verdict.CLEAR:
        return None

    reason = _reason_text(decisions)
    if verdict is Verdict.BLOCK:
        return _output("deny", "Customs blocked this install.\n" + reason)
    return _output("ask", "Customs needs your approval before this runs.\n" + reason)


def run(stdin: TextIO, stdout: TextIO) -> int:
    try:
        payload = json.load(stdin)
        response = handle(payload)
    except Exception as err:
        response = _output("ask", f"Customs could not check this command: {err}")
    if response is not None:
        json.dump(response, stdout)
    return 0
