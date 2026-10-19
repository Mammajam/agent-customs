"""Turn inspected facts into a verdict for one declaration.

Verdicts:
    CLEAR    proceed
    INSPECT  stop and ask the developer before proceeding
    BLOCK    refuse; the agent gets the reason and a suggested real name

Rules are deterministic and fail safe: when a fact cannot be checked, the
verdict is INSPECT, never CLEAR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from customs.parser import Declaration, Ecosystem
from customs.registry import PackageFacts
from customs.typos import MAX_TYPO_DISTANCE

NEW_PACKAGE_DAYS = 30
YOUNG_NEAR_MISS_DAYS = 180
LOW_WEEKLY_DOWNLOADS = 100
LOW_STARS = 5


class Verdict(str, Enum):
    CLEAR = "clear"
    INSPECT = "inspect"
    BLOCK = "block"


_RANK = {Verdict.CLEAR: 0, Verdict.INSPECT: 1, Verdict.BLOCK: 2}


@dataclass
class Decision:
    declaration: Declaration
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)
    suggestion: str | None = None

    def add(self, verdict: Verdict, reason: str) -> None:
        self.reasons.append(reason)
        if _RANK[verdict] > _RANK[self.verdict]:
            self.verdict = verdict


def _age_days(facts: PackageFacts, now: datetime) -> float | None:
    if facts.first_published is None:
        return None
    return (now - facts.first_published).total_seconds() / 86400


def judge(decl: Declaration, facts: PackageFacts, now: datetime | None = None) -> Decision:
    now = now or datetime.now(timezone.utc)
    decision = Decision(decl, Verdict.CLEAR)

    if not facts.exists:
        decision.add(Verdict.BLOCK, f"{decl.name} does not exist on {decl.ecosystem.value}")
        if facts.typo_of:
            decision.suggestion = facts.typo_of  # shown separately as "did you mean"
        return decision

    if facts.vulnerability_ids:
        listed = ", ".join(facts.vulnerability_ids[:5])
        if decl.version:
            decision.add(Verdict.INSPECT, f"advisories affect {decl.version}: {listed}")
        else:
            # Unpinned: advisories exist for old versions. Note them, don't ask.
            decision.reasons.append(f"{len(facts.vulnerability_ids)} advisories on past versions")

    age = _age_days(facts, now)
    if facts.typo_of and facts.typo_distance is not None:
        if age is not None and age < YOUNG_NEAR_MISS_DAYS:
            decision.add(Verdict.BLOCK, f"young package one edit away from {facts.typo_of}")
            decision.suggestion = facts.typo_of
        else:
            decision.add(Verdict.INSPECT, f"name is close to popular package {facts.typo_of}")
            decision.suggestion = facts.typo_of

    if age is None:
        decision.add(Verdict.INSPECT, "publish date unknown")
    elif age < NEW_PACKAGE_DAYS:
        decision.add(Verdict.INSPECT, f"published {int(age)} days ago")

    if decl.ecosystem is Ecosystem.NPM:
        if facts.weekly_downloads is None:
            decision.add(Verdict.INSPECT, "download count unknown")
        elif facts.weekly_downloads < LOW_WEEKLY_DOWNLOADS:
            decision.add(Verdict.INSPECT, f"only {facts.weekly_downloads} weekly downloads")

    if facts.archived:
        decision.add(Verdict.INSPECT, "repository is archived")
    if facts.stars is not None and facts.stars < LOW_STARS:
        decision.add(Verdict.INSPECT, f"only {facts.stars} stars")

    if decl.ecosystem is Ecosystem.NPM and facts.maintainers == 0:
        decision.add(Verdict.INSPECT, "no maintainer listed")

    return decision


def unverified(decl: Declaration, reason: str) -> Decision:
    """A declaration Customs cannot check yet. It asks rather than passes."""
    return Decision(decl, Verdict.INSPECT, [reason])
