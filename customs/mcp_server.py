"""Minimal MCP server over stdio exposing one tool: customs.check.

Speaks JSON-RPC 2.0, one message per line, which is how MCP clients launch a
stdio server. Standard library only.

Register in a client's MCP config as:
    {"command": "python3", "args": ["-m", "customs.mcp_server"]}

Tool: customs.check
    input:  {"command": "pip install reqeusts"}
    output: text with each declaration's verdict, reasons and suggestions,
            plus "overall" (clear | inspect | block)
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from customs import allowlist
from customs.checkpoint import check_command, overall

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "customs", "version": "0.1.0"}

TOOL = {
    "name": "customs.check",
    "description": (
        "Check a shell command before it runs. Installs, git clones and skill fetches are "
        "verified against package registries and GitHub. Returns clear, inspect or block, "
        "with reasons and a suggested real name for a block."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "The shell command to check"}},
        "required": ["command"],
    },
}


def _result_text(command: str) -> dict[str, Any]:
    decisions = check_command(command, allow=allowlist.load())
    if not decisions:
        return {"overall": "clear", "text": "No installs, clones or skill fetches found."}
    lines = []
    for d in decisions:
        lines.append(f"{d.verdict.value.upper()} {d.declaration.ecosystem.value} {d.declaration.name}")
        lines += [f"  - {r}" for r in d.reasons]
        if d.suggestion:
            lines.append(f"  did you mean: {d.suggestion}")
    return {"overall": overall(decisions).value, "text": "\n".join(lines)}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    """Return the JSON-RPC response for a request, or None for a notification."""
    method = message.get("method")
    msg_id = message.get("id")
    if msg_id is None:  # notifications such as notifications/initialized get no reply
        return None

    if method == "initialize":
        result: Any = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "tools/list":
        result = {"tools": [TOOL]}
    elif method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != TOOL["name"]:
            return _error(msg_id, -32602, f"unknown tool: {params.get('name')}")
        command = str((params.get("arguments") or {}).get("command", ""))
        if not command:
            return _error(msg_id, -32602, "command is required")
        try:
            out = _result_text(command)
        except Exception as err:  # a checkpoint failure must not read as a pass
            out = {"overall": "inspect", "text": f"Customs could not check this command: {err}"}
        result = {
            "content": [{"type": "text", "text": out["text"]}],
            "structuredContent": {"overall": out["overall"]},
            "isError": False,
        }
    elif method == "ping":
        result = {}
    else:
        return _error(msg_id, -32601, f"method not found: {method}")
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def serve(stdin: TextIO, stdout: TextIO) -> int:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            response = _error(None, -32700, "parse error")
        else:
            response = handle(message)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(serve(sys.stdin, sys.stdout))
