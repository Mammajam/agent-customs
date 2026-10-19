"""Project allowlist for false blocks and approvals the team has already made.

File: .customs/allowlist.json in the project root

    {"allow": ["internal-pkg", "left-pad"]}

An allowlisted name lifts an INSPECT verdict to CLEAR. It never lifts a BLOCK,
so a name that does not exist cannot be waved through.
"""

from __future__ import annotations

import json
from pathlib import Path

ALLOWLIST_PATH = Path(".customs") / "allowlist.json"


def load(root: Path | None = None) -> frozenset[str]:
    path = (root or Path.cwd()) / ALLOWLIST_PATH
    try:
        names = json.loads(path.read_text()).get("allow", [])
    except (OSError, ValueError, AttributeError):
        return frozenset()
    return frozenset(str(n).lower() for n in names)
