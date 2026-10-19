"""Remediation loop: patch a manifest with real names, then prove it with tests.

For each BLOCK that carries a suggestion, the hallucinated name is replaced in
the manifest. The suggestion is checked again before it is written. The test
command then runs. If the tests fail, the original manifest is restored, so a
bad fix never stays on disk.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from customs.checkpoint import check_command, overall
from customs.verdict import Decision, Verdict

TEST_TIMEOUT_SECONDS = 300


@dataclass
class Remediation:
    manifest: Path
    replacements: dict[str, str] = field(default_factory=dict)
    status: str = "nothing to fix"  # fixed | tests-failed | unverified-suggestion | nothing to fix
    test_output: str = ""
    notes: list[str] = field(default_factory=list)


def plan_replacements(decisions: list[Decision], registry=None,
                      now=None) -> tuple[dict[str, str], list[str]]:
    """Map each blocked name with a suggestion to that suggestion, if the suggestion checks clean."""
    replacements: dict[str, str] = {}
    notes: list[str] = []
    for d in decisions:
        if d.verdict is not Verdict.BLOCK or not d.suggestion:
            continue
        check = check_command(_install_line(d, d.suggestion), registry, now)
        if overall(check) is Verdict.CLEAR:
            replacements[d.declaration.name] = d.suggestion
        else:
            notes.append(f"suggestion {d.suggestion} for {d.declaration.name} is not clean; left unchanged")
    return replacements, notes


def _install_line(d: Decision, name: str) -> str:
    """Re-check the replacement with the same version the manifest pins, not just the name."""
    spec = d.declaration.specifier
    if d.declaration.ecosystem.value == "npm":
        return f"npm install {name}" + (f"@{spec}" if spec else "")
    return f"pip install {name}{spec}"


def patch_requirements(text: str, replacements: dict[str, str]) -> str:
    out = []
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        match = re.match(r"^(\s*)([A-Za-z0-9][A-Za-z0-9._-]*)(.*)$", body)
        if match and match.group(2) in replacements:
            out.append(f"{match.group(1)}{replacements[match.group(2)]}{match.group(3)}{ending}")
        else:
            out.append(line)
    return "".join(out)


def patch_package_json(text: str, replacements: dict[str, str]) -> str:
    doc = json.loads(text)
    for section in ("dependencies", "devDependencies"):
        deps = doc.get(section, {})
        for bad, good in replacements.items():
            if bad in deps:
                deps[good] = deps.pop(bad)
    return json.dumps(doc, indent=2) + "\n"


def apply_fix(manifest: Path, decisions: list[Decision], test_command: str,
              registry=None, cwd: Path | None = None, now=None) -> Remediation:
    result = Remediation(manifest=manifest)
    result.replacements, result.notes = plan_replacements(decisions, registry, now)
    if not result.replacements:
        return result

    original = manifest.read_text()
    if manifest.name == "package.json":
        patched = patch_package_json(original, result.replacements)
    else:
        patched = patch_requirements(original, result.replacements)
    manifest.write_text(patched)

    proc = subprocess.run(test_command, shell=True, cwd=cwd or manifest.parent,
                          capture_output=True, text=True, timeout=TEST_TIMEOUT_SECONDS)
    result.test_output = (proc.stdout + proc.stderr)[-4000:]
    if proc.returncode == 0:
        result.status = "fixed"
    else:
        manifest.write_text(original)
        result.status = "tests-failed"
        result.notes.append("tests failed after the patch; original manifest restored")
    return result
