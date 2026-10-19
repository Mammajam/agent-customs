"""Gate 1 check: one call to Nemotron through Nebius Token Factory.

Usage:
    NEBIUS_API_KEY=... python3 scripts/gate1_check.py            # list models
    NEBIUS_API_KEY=... CUSTOMS_MODEL_NANO=<id> python3 scripts/gate1_check.py

Exit codes: 0 pass, 1 call failed, 2 not configured yet.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from customs.llm import Settings, TokenFactory, TokenFactoryError  # noqa: E402


def main() -> int:
    try:
        settings = Settings.from_env()
    except TokenFactoryError as err:
        print(f"NOT CONFIGURED: {err}")
        return 2

    client = TokenFactory(settings)
    try:
        models = client.list_models()
    except Exception as err:  # network or auth failure
        print(f"FAIL: could not list models: {err}")
        return 1

    nemotron = [m for m in models if "nemotron" in m.lower()]
    print(f"Models visible to this key: {len(models)}")
    print("Nemotron IDs:")
    for model_id in nemotron or ["(none listed)"]:
        print(f"  {model_id}")

    try:
        model = client.require_model("nano")
    except TokenFactoryError:
        print("Set CUSTOMS_MODEL_NANO to one of the IDs above, then rerun to make the call.")
        return 2

    try:
        reply = client.chat(model, [{"role": "user", "content": "Reply with the word: ready"}], max_tokens=16)
    except Exception as err:
        print(f"FAIL: chat call to {model} failed: {err}")
        return 1
    print(f"PASS: {model} replied: {reply.strip()!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
