"""Run the full check on one shell command: parse, inspect, judge."""

from __future__ import annotations

import re
from datetime import datetime

from customs.parser import Declaration, Ecosystem, parse_command
from customs.registry import RegistryClient
from customs.verdict import Decision, Verdict, judge, unverified

GITHUB_SOURCE_RE = re.compile(r"^https?://github\.com/([^/\s]+/[^/\s#?]+)")


def github_name(decl: Declaration) -> str | None:
    """The github.com/owner/repo form of a git or skill source, if it is on GitHub."""
    if decl.ecosystem is Ecosystem.GIT and decl.name.startswith("github.com/"):
        return decl.name
    if decl.ecosystem is Ecosystem.SKILL:
        match = GITHUB_SOURCE_RE.match(decl.name)
        if match:
            return "github.com/" + match.group(1).removesuffix(".git")
    return None


def check_command(command: str, registry: RegistryClient | None = None,
                  now: datetime | None = None, allow: frozenset[str] = frozenset()) -> list[Decision]:
    registry = registry or RegistryClient()
    result = parse_command(command)
    decisions: list[Decision] = []

    for decl in result.declarations:
        repo = github_name(decl)
        if decl.ecosystem in (Ecosystem.GIT, Ecosystem.SKILL) and repo is None:
            # Non-GitHub sources have no inspector yet. They ask rather than pass.
            decisions.append(unverified(decl, f"{decl.ecosystem.value} source not inspected yet"))
            continue
        try:
            if repo is not None:
                facts = registry.inspect(Ecosystem.GIT, repo)
            else:
                facts = registry.inspect(decl.ecosystem, decl.name, decl.version)
        except Exception as err:  # network failure must not become a pass
            decisions.append(unverified(decl, f"registry lookup failed: {err}"))
            continue
        decision = judge(decl, facts, now)
        if decision.verdict is Verdict.INSPECT and decl.name.lower() in allow:
            # The project has allowlisted this name. Only INSPECT is lifted; BLOCK stands.
            decision.verdict = Verdict.CLEAR
            decision.reasons.append("allowlisted by project policy")
        decisions.append(decision)

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
