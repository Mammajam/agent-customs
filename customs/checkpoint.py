"""Run the full check on one shell command: parse, inspect, judge."""

from __future__ import annotations

import re
from datetime import datetime

from customs import llm_checks, xray
from customs.llm import Settings, TokenFactory, TokenFactoryError
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


_FROM_ENV = object()


def llm_from_env() -> TokenFactory | None:
    """A Token Factory client when NEBIUS_API_KEY is set, otherwise None (LLM steps off)."""
    try:
        return TokenFactory(Settings.from_env())
    except TokenFactoryError:
        return None


def check_command(command: str, registry: RegistryClient | None = None,
                  now: datetime | None = None, allow: frozenset[str] = frozenset(),
                  xray_enabled: bool = True, xray_fetch=None,
                  llm: TokenFactory | None | object = _FROM_ENV) -> list[Decision]:
    registry = registry or RegistryClient()
    if llm is _FROM_ENV:
        llm = llm_from_env()
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
        if xray_enabled and facts.exists and decl.ecosystem in (Ecosystem.PYPI, Ecosystem.NPM):
            _apply_xray(decision, facts, xray_fetch)
        if llm is not None:
            _apply_llm(decision, facts, llm)
        if decision.verdict is Verdict.INSPECT and decl.name.lower() in allow:
            # The project has allowlisted this name. Only INSPECT is lifted; BLOCK stands.
            decision.verdict = Verdict.CLEAR
            decision.reasons.append("allowlisted by project policy")
        decisions.append(decision)

    for item in result.unparsed:
        decisions.append(unverified(_placeholder(command), f"not checked: {item}"))

    return decisions


def _apply_xray(decision: Decision, facts, fetch) -> None:
    """Static X-ray of install-time code. Findings and failures both ask; neither blocks."""
    result = xray.scan(facts, fetch) if fetch else xray.scan(facts)
    for finding in result.findings:
        decision.add(Verdict.INSPECT, f"x-ray: {finding}")
    if result.error:
        decision.add(Verdict.INSPECT, f"x-ray could not run: {result.error}")
    for skipped in result.skipped:
        # Visible but not a verdict change: a large package is not a reason to ask.
        decision.reasons.append(f"x-ray skipped: {skipped}")


def _apply_llm(decision: Decision, facts, client: TokenFactory) -> None:
    """Nemotron second opinion. It can raise a verdict to INSPECT, never lower one.

    BLOCK stays with the deterministic rules. A failed or unreadable model call
    is noted and changes nothing, so the LLM steps cannot turn a stop into a pass.
    """
    if decision.verdict is not Verdict.CLEAR:
        triage = llm_checks.triage(client, decision.declaration.name, "; ".join(decision.reasons))
        decision.reasons.append(f"nemotron triage: {triage.verdict.value}: {triage.reason}")
    if facts.install_scripts:
        text = "\n".join(f"{hook}: {body}" for hook, body in facts.install_scripts.items())
        scan = llm_checks.injection_scan(client, text)
        if scan.suspicious:
            decision.add(Verdict.INSPECT, f"nemotron injection scan: {scan.reason}")


def overall(decisions: list[Decision]) -> Verdict:
    if any(d.verdict is Verdict.BLOCK for d in decisions):
        return Verdict.BLOCK
    if any(d.verdict is Verdict.INSPECT for d in decisions):
        return Verdict.INSPECT
    return Verdict.CLEAR


def _placeholder(command: str) -> Declaration:
    """Stand-in declaration for text the parser could not read."""
    return Declaration(Ecosystem.PYPI, command, source=command)
