"""Static X-ray: read the install-time code of a package. Never execute it.

This is the fallback the plan names for the sandboxed X-ray. It inspects only
code that runs during install:

- npm: lifecycle scripts (preinstall, install, postinstall, prepare)
- PyPI sdist: setup.py, which pip runs when building from source
- PyPI wheel: .pth files, which Python runs at every interpreter start

Downloads are size-capped and read in memory. Archives are read, not extracted,
so there is no path-traversal or write risk on the developer's machine.

Findings are reasons to ask, not proof of malice. A scan that cannot run is
reported as an error, and the caller treats that as INSPECT, never as a pass.
"""

from __future__ import annotations

import io
import re
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from typing import Callable

from customs.registry import PackageFacts, USER_AGENT

MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024
MAX_READ_BYTES = 256 * 1024
TIMEOUT_SECONDS = 20

# Each pattern describes a behaviour, so the reason says what the code does.
SIGNALS = [
    (re.compile(r"(curl|wget)[^\n|;]*\|\s*(ba|z|da)?sh\b"), "pipes a download into a shell"),
    (re.compile(r"base64\s+(-d|--decode)|b64decode\(|atob\("), "decodes an encoded payload"),
    (re.compile(r"\beval\s*\(|\bexec\s*\(|new Function\("), "evaluates dynamic code"),
    (re.compile(r"os\.system\(|subprocess\.|child_process|execSync\(|spawnSync\("), "runs a shell command"),
    (re.compile(r"urllib\.request|requests\.(get|post|put)\(|socket\.socket\(|https?\.request\(|fetch\("),
     "makes a network request"),
    (re.compile(r"(\\x[0-9a-fA-F]{2}){8,}"), "contains a long hex-escaped string"),
]

Fetch = Callable[[str, int], bytes]


@dataclass
class XrayResult:
    findings: list[str] = field(default_factory=list)  # reasons to ask
    scanned: list[str] = field(default_factory=list)  # what was read
    skipped: list[str] = field(default_factory=list)  # too large or absent, not a finding
    error: str | None = None  # the scan could not run; the caller asks


def scan_text(text: str, where: str) -> list[str]:
    hits = [f"{where} {reason}" for pattern, reason in SIGNALS if pattern.search(text)]
    return hits


def scan_npm(scripts: dict[str, str]) -> XrayResult:
    # Most packages with install scripts are benign (native builds). Only a
    # suspicious behaviour inside the script is a finding.
    result = XrayResult()
    for hook, body in scripts.items():
        result.scanned.append(f"npm {hook} script")
        result.findings += scan_text(body, f"{hook} script")
    return result


def _read_limited(data: bytes) -> str:
    return data[:MAX_READ_BYTES].decode("utf-8", "replace")


def scan_sdist(data: bytes) -> XrayResult:
    result = XrayResult()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
            for member in archive.getmembers():
                if member.isfile() and member.name.count("/") == 1 and member.name.endswith("/setup.py"):
                    handle = archive.extractfile(member)
                    text = _read_limited(handle.read(MAX_READ_BYTES)) if handle else ""
                    result.scanned.append("sdist setup.py")
                    result.findings += scan_text(text, "setup.py")
                    return result
    except (tarfile.TarError, OSError, EOFError) as err:
        result.error = f"sdist could not be read: {err}"
        return result
    result.skipped.append("sdist has no top-level setup.py")
    return result


def scan_wheel(data: bytes) -> XrayResult:
    result = XrayResult()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.filename.endswith(".pth") and "/" not in info.filename:
                    body = _read_limited(archive.read(info))
                    result.scanned.append(f"wheel {info.filename}")
                    # Many packages ship .pth files for namespaces. Only a behaviour in one is a finding.
                    result.findings += scan_text(body, info.filename)
    except (zipfile.BadZipFile, OSError) as err:
        result.error = f"wheel could not be read: {err}"
    return result


def _merge(into: XrayResult, other: XrayResult) -> XrayResult:
    into.findings += other.findings
    into.scanned += other.scanned
    into.skipped += other.skipped
    if other.error:
        into.error = other.error
    return into


def fetch_bytes(url: str, limit: int = MAX_DOWNLOAD_BYTES) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        declared = int(response.headers.get("Content-Length") or 0)
        if declared > limit:
            raise OverflowError(f"artifact is {declared} bytes, over the {limit} byte limit")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise OverflowError(f"artifact is over the {limit} byte limit")
        return data


def scan(facts: PackageFacts, fetch: Fetch = fetch_bytes) -> XrayResult:
    """Scan the install-time code for one package. Read-only."""
    result = XrayResult()
    if facts.install_scripts:
        _merge(result, scan_npm(facts.install_scripts))

    if facts.sdist_url:
        try:
            _merge(result, scan_sdist(fetch(facts.sdist_url, MAX_DOWNLOAD_BYTES)))
        except OverflowError as err:
            result.skipped.append(f"sdist: {err}")
        except OSError as err:
            result.error = f"sdist download failed: {err}"

    if facts.wheel_urls:  # one wheel is enough to read the package's .pth files
        try:
            _merge(result, scan_wheel(fetch(facts.wheel_urls[0], MAX_DOWNLOAD_BYTES)))
        except OverflowError as err:
            result.skipped.append(f"wheel: {err}")
        except OSError as err:
            result.error = f"wheel download failed: {err}"

    return result
