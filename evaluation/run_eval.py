"""Evaluation harness: catch rate, false-block rate and latency.

    python3 evaluation/run_eval.py

Runs every case in evaluation/corpus.json through the live checkpoint and writes
evaluation/results.json. Exit 0 always; read the numbers, do not gate on them.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from customs.checkpoint import check_command, overall  # noqa: E402
from customs.verdict import Verdict  # noqa: E402

CORPUS = ROOT / "evaluation" / "corpus.json"
RESULTS = ROOT / "evaluation" / "results.json"


def run() -> dict:
    cases = json.loads(CORPUS.read_text())["cases"]
    rows = []
    for case in cases:
        start = time.perf_counter()
        verdict = overall(check_command(case["command"]))
        elapsed_ms = (time.perf_counter() - start) * 1000
        rows.append({
            "command": case["command"],
            "expect": case["expect"],
            "verdict": verdict.value,
            "latency_ms": round(elapsed_ms, 1),
        })

    attacks = [r for r in rows if r["expect"] == "block"]
    clean = [r for r in rows if r["expect"] == "clear"]
    caught = sum(r["verdict"] == Verdict.BLOCK.value for r in attacks)
    false_blocks = sum(r["verdict"] == Verdict.BLOCK.value for r in clean)
    latencies = sorted(r["latency_ms"] for r in rows)

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cases": len(rows),
        "catch_rate": round(caught / len(attacks), 3) if attacks else None,
        "caught": caught,
        "attacks": len(attacks),
        "false_block_rate": round(false_blocks / len(clean), 3) if clean else None,
        "false_blocks": false_blocks,
        "clean": len(clean),
        "latency_ms_median": round(statistics.median(latencies), 1),
        "latency_ms_p95": round(latencies[int(0.95 * (len(latencies) - 1))], 1),
        "missed": [r["command"] for r in attacks if r["verdict"] != Verdict.BLOCK.value],
        "false_blocked": [r["command"] for r in clean if r["verdict"] == Verdict.BLOCK.value],
    }
    RESULTS.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
