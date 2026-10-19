"""Registry inspection: gather facts about a package before any verdict.

Sources are the public PyPI JSON API, the npm registry and downloads API, and
the OSV vulnerability database. Every lookup goes through an injectable
fetcher so the logic can be tested without the network.

This module reports facts only. Turning them into a verdict is the verdict
engine's job.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from customs.parser import Ecosystem
from customs.typos import closest_popular

USER_AGENT = "customs/0.1 (hackathon checkpoint; +https://github.com/Mammajam/agent-customs)"
TIMEOUT_SECONDS = 10

PYPI_URL = "https://pypi.org/pypi/{name}/json"
NPM_URL = "https://registry.npmjs.org/{name}"
NPM_DOWNLOADS_URL = "https://api.npmjs.org/downloads/point/last-week/{name}"
OSV_URL = "https://api.osv.dev/v1/query"

Fetcher = Callable[[str, dict | None], Any]


def fetch_json(url: str, body: dict | None = None) -> Any:
    """GET (or POST when body is given) a JSON document. Returns None on 404."""
    data = None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


@dataclass
class PackageFacts:
    ecosystem: Ecosystem
    name: str
    exists: bool
    first_published: datetime | None = None
    latest_version: str | None = None
    maintainers: int | None = None
    weekly_downloads: int | None = None
    vulnerability_ids: list[str] = field(default_factory=list)
    typo_of: str | None = None
    typo_distance: int | None = None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    # PyPI and npm both use ISO 8601; 'Z' suffixes need converting for fromisoformat.
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class RegistryClient:
    def __init__(self, fetch: Fetcher = fetch_json):
        self._fetch = fetch

    def inspect(self, ecosystem: Ecosystem, name: str, version: str | None = None) -> PackageFacts:
        if ecosystem is Ecosystem.PYPI:
            facts = self._pypi(name)
            osv_ecosystem = "PyPI"
        elif ecosystem is Ecosystem.NPM:
            facts = self._npm(name)
            osv_ecosystem = "npm"
        else:
            raise ValueError(f"no registry for ecosystem {ecosystem.value}")

        if facts.exists:
            facts.vulnerability_ids = self._osv(osv_ecosystem, name, version)
        facts.typo_of, facts.typo_distance = closest_popular(name, ecosystem.value)
        return facts

    def _pypi(self, name: str) -> PackageFacts:
        doc = self._fetch(PYPI_URL.format(name=urllib.parse.quote(name)), None)
        if doc is None:
            return PackageFacts(Ecosystem.PYPI, name, exists=False)
        uploads = [
            _parse_time(f.get("upload_time_iso_8601"))
            for files in doc.get("releases", {}).values()
            for f in files
        ]
        uploads = [u for u in uploads if u]
        info = doc.get("info", {})
        # PyPI JSON has no maintainer list. Named contacts are a weak proxy, and
        # an empty field means unknown, not zero.
        contacts = {c for c in (info.get("author"), info.get("maintainer")) if c}
        return PackageFacts(
            Ecosystem.PYPI,
            name,
            exists=True,
            first_published=min(uploads) if uploads else None,
            latest_version=info.get("version"),
            maintainers=len(contacts) if contacts else None,
        )

    def _npm(self, name: str) -> PackageFacts:
        doc = self._fetch(NPM_URL.format(name=urllib.parse.quote(name, safe="@")), None)
        if doc is None:
            return PackageFacts(Ecosystem.NPM, name, exists=False)
        downloads = self._fetch(NPM_DOWNLOADS_URL.format(name=urllib.parse.quote(name, safe="@")), None)
        return PackageFacts(
            Ecosystem.NPM,
            name,
            exists=True,
            first_published=_parse_time(doc.get("time", {}).get("created")),
            latest_version=doc.get("dist-tags", {}).get("latest"),
            maintainers=len(doc.get("maintainers", [])),
            weekly_downloads=(downloads or {}).get("downloads"),
        )

    def _osv(self, ecosystem: str, name: str, version: str | None = None) -> list[str]:
        query: dict[str, Any] = {"package": {"name": name, "ecosystem": ecosystem}}
        if version:
            query["version"] = version  # only advisories affecting this version
        doc = self._fetch(OSV_URL, query)
        return [v["id"] for v in (doc or {}).get("vulns", []) if "id" in v]
