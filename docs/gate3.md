# Gate 3 checklist (code freeze, 27 October)

Gate 3 passes when the public demo URL works from a fresh browser and the evaluation numbers are recorded. After it, only the video and write-up are worked on.

## Status

| Item | Status | Evidence or blocker |
|---|---|---|
| Parser for pip, npm, git clone, gh clone, skill add | Built, tested | `customs/parser.py`, `tests/test_parser.py` |
| Registry checks: PyPI, npm, OSV advisories | Built, tested, live-checked | `customs/registry.py`, `customs/verdict.py` |
| GitHub repository and skill source checks | Built, tested, live-checked | `customs/registry.py` (`_github`), `customs/checkpoint.py` |
| Verdict engine: CLEAR, INSPECT, BLOCK | Built, tested | `customs/verdict.py` |
| Claude Code PreToolUse hook | Built, live in a session | `.claude/settings.json`, `customs/hook.py`. Denied a hallucinated install on 19 Oct |
| Remediation loop: patch, re-check, re-run tests, roll back | Built, tested, live-checked | `customs/remediate.py`, `customs fix` |
| Allowlist for false blocks (risk-register mitigation) | Built, tested | `customs/allowlist.py`, `.customs/allowlist.json` |
| Evaluation harness: catch rate, false-block rate, latency | Built, run | `evaluation/run_eval.py`, `evaluation/results.json`. 12/12 caught, 0/10 false blocks |
| Dashboard with try-a-package box | Built, tested, served locally | `customs/web.py`. POST `/check` returns a verdict |
| Dockerfile for the dashboard | Written, not built | `Dockerfile`. Docker not run in this environment |
| Public demo URL, free to test until 15 December | **Not done** | Needs deployment. The plan calls for a Nebius Serverless Endpoint, which needs Token Factory access (Gate 1 blocker) |
| Nemotron triage and injection scan | Built, tested with fake transport | `customs/llm_checks.py`. **Not run live**: no API key yet |
| Tavily provenance lookup | Built, tested with fake transport | `customs/llm_checks.py`. **Not run live**: no Tavily key |
| Sandbox X-ray on Serverless Jobs | **Not built** | Plan says Thursday, time-boxed to 6 hours, with a static fallback. Blocked on Serverless Jobs access |
| MCP server exposing `customs.check` | **Not built** | Should item, after the MVP |
| GitHub Action for CI | **Not built** | Could item |
| Feedback log | Started | `FEEDBACK.md` |
| Evaluation corpus breadth | Partial | 22 cases. The fabricated names are absent from PyPI, so the corpus does not test malicious packages that exist |

## Blockers before the freeze

1. Token Factory API key (Gate 1). Needed for live triage, injection scan and the Nemotron model IDs.
2. Tavily API key, for provenance.
3. A host for the public URL. The plan names Nebius Serverless Endpoint. The Dockerfile is ready for any container host.

## Known limits, stated in the README and video

- Typo checks use a seed list of about 40 popular names per ecosystem.
- PyPI has no maintainer list, so maintainer checks are skipped for PyPI.
- Non-GitHub git sources and skills from other hosts ask for approval; they are not inspected.
- The evaluation corpus measures the does-not-exist path, not detection of malicious packages that exist.
