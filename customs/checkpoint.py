"""Run the full check on one shell command: parse, inspect, judge."""

from __future__ import annotations

from datetime import datetime

from customs.parser import Declaration, Ecosystem, parse_command
from customs.registry import RegistryClient
from customs.verdict import Decision, Verdict, judge, unverified

# Git and skill sources have no inspector yet (X-ray lands later in the build).
# They ask the developer rather than pass silently.
UNINSPECTED = {Ecosystem.GIT, Ecosystem.SKILL}


def check_command(command: str, registry: RegistryClient | None = None,
                  now: datetime | None = None) -> list[Decision]:
    registry = registry or RegistryClient()
    result = parse_command(command)
    decisions: list[Decision] = []

    for decl in result.declarations:
        if decl.ecosystem in UNINSPECTED:
            decisions.append(unverified(decl, f"{decl.ecosystem.value} source not inspected yet"))
            continue
        try:
            facts = registry.inspect(decl.ecosystem, decl.name, decl.version)
        except Exception as err:  # network failure must not become a pass
            decisions.append(unverified(decl, f"registry lookup failed: {err}"))
            continue
        decisions.append(judge(decl, facts, now))

    for item in result.unparsed:
        decisions.append(unverified(_placeholder(command), f"not checked: {item}"))

    return decisions


def overall(decisions: list[Decision]) -> Verdict:
    if any(d.verdict is Verdict.BLOCK for d in decisions):
        return Verdict.BLOCK
    if any(d.verdict is Verdict.INSPECT for d in decisions):
        return Verdict.INSPECT
    return Verdict.CLEAR


def _placeholder(command: str) -> Declaration:
    """Stand-in declaration for text the parser could not read."""
    return Declaration(Ecosystem.PYPI, command, source=command)
