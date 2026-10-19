"""Minimal client for the Nebius Token Factory OpenAI-compatible API.

Standard library only. Configuration comes from the environment:

    NEBIUS_API_KEY              bearer token (required to call the API)
    CUSTOMS_TF_BASE_URL         defaults to https://api.tokenfactory.nebius.com/v1/
    CUSTOMS_MODEL_NANO          triage model ID (set once confirmed from /v1/models)
    CUSTOMS_MODEL_SUPER         intent-resolution / remediation model ID
    CUSTOMS_MODEL_ULTRA         injection-scan model ID

Model IDs are never hard-coded: they are read from config so a catalogue change
does not need a code change.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
TIMEOUT_SECONDS = 60

Transport = Callable[[str, dict | None, dict], Any]


class TokenFactoryError(RuntimeError):
    """Raised for missing configuration or a failed API call."""


def http_transport(url: str, body: dict | None, headers: dict) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read())


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    nano: str | None = None
    super: str | None = None
    ultra: str | None = None

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Settings":
        env = os.environ if env is None else env
        api_key = env.get("NEBIUS_API_KEY", "")
        if not api_key:
            raise TokenFactoryError("NEBIUS_API_KEY is not set")
        base_url = env.get("CUSTOMS_TF_BASE_URL", DEFAULT_BASE_URL)
        if not base_url.endswith("/"):
            base_url += "/"
        return cls(
            api_key=api_key,
            base_url=base_url,
            nano=env.get("CUSTOMS_MODEL_NANO") or None,
            super=env.get("CUSTOMS_MODEL_SUPER") or None,
            ultra=env.get("CUSTOMS_MODEL_ULTRA") or None,
        )


class TokenFactory:
    def __init__(self, settings: Settings, transport: Transport = http_transport):
        self.settings = settings
        self._transport = transport

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "customs/0.1",
        }

    def list_models(self) -> list[str]:
        doc = self._transport(self.settings.base_url + "models", None, self._headers())
        return [m["id"] for m in doc.get("data", []) if "id" in m]

    def chat(self, model: str, messages: list[dict], max_tokens: int = 512, temperature: float = 0.0) -> str:
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        doc = self._transport(self.settings.base_url + "chat/completions", body, self._headers())
        try:
            return doc["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as err:
            raise TokenFactoryError(f"unexpected response shape: {doc!r}") from err

    def require_model(self, tier: str) -> str:
        model = getattr(self.settings, tier)
        if not model:
            raise TokenFactoryError(f"CUSTOMS_MODEL_{tier.upper()} is not set")
        return model
