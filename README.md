# Customs

Customs is an agent-native dependency checkpoint. It sits between a coding agent and the shell, and checks every package install, repository clone and skill fetch before anything runs.

Status: early build (Day 1 of the hackathon plan). The declaration parser is the first component; the registry checks, Nemotron triage, sandbox X-ray and remediation loop come next.

## How it fits together

1. **Declare**: parse the agent's command into declarations (`pip`, `npm`, `git clone`, skill URLs).
2. **Inspect**: check registries and provenance (planned).
3. **X-ray**: run the artifact in a sandbox (planned, Nebius Serverless Jobs).
4. **Decide**: clear, inspect or quarantine (planned).
5. **Remediate**: suggest the real package, patch the code and re-run tests (planned).

## Claude Code hook

`.claude/settings.json` registers `customs hook` as a PreToolUse hook on Bash calls. A blocked install is denied with a suggested real name; an unverified one asks for approval.

Try it from the terminal:

```bash
python3 -m customs.cli check "pip install reqeusts"
```

## Dashboard and evaluation

```bash
python3 evaluation/run_eval.py   # catch rate, false-block rate, latency -> evaluation/results.json
python3 -m customs.web           # dashboard on http://127.0.0.1:8000 with a "try a package" box
```

The corpus in `evaluation/corpus.json` is small, and its fabricated names do not exist on PyPI. It measures the does-not-exist path, not detection of malicious packages that do exist.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Install `requests` into the project venv (system Python is externally managed):

```bash
python3 -m venv .venv && .venv/bin/python -m pip install requests
```

## How we use Nebius and NVIDIA

```
agent command
     |
     v
 parse (pip, npm, git, skills) ---> registries: PyPI, npm, OSV, GitHub   (built)
     |
     v
 verdict: CLEAR | INSPECT | BLOCK
     |                                        
     +--> triage: Nemotron Nano  (Token Factory)   built and wired in, not run live*
     +--> injection scan: Nemotron Ultra            built and wired in, not run live*
     +--> provenance: Tavily search                 built, not run live
     +--> X-ray: static read of install-time code   built
     +--> X-ray: sandboxed run on Nebius Serverless Jobs   planned
     |
     v
 hook (deny / ask) | fix (patch manifest, re-run tests) | dashboard (Serverless Endpoint, planned)
```

- **Token Factory** (Nebius) is the model endpoint for the LLM steps. Model IDs come from config, read from `/v1/models`. The checkpoint calls it automatically when `NEBIUS_API_KEY` is set (`customs/checkpoint.py`); without a key the LLM steps are off and the deterministic verdicts are unchanged. A model can raise a verdict to INSPECT but never lower one.
- **Nemotron** on Token Factory: Nano for triage, Super for intent resolution, Ultra for injection scanning.
- **Serverless Jobs** (planned): untrusted packages are inspected in an isolated container, never on the developer's machine.
- **Serverless Endpoint** (planned): hosts the dashboard with scale-to-zero, so the demo stays live until judging ends. The dashboard runs on Vercel for now.

**\* Why none of this has run live.** The author is in Liberia, which is not in the country list of the Nebius Token Factory billing form, so no API key could be created. The Nebius client, the Nemotron prompts and the checkpoint wiring are built and tested against a fake transport (`tests/test_llm.py`, `tests/test_llm_checks.py`, `tests/test_checkpoint_llm.py`). Nothing here claims a live Nebius or NVIDIA result. With a key, `NEBIUS_API_KEY=... python3 scripts/gate1_check.py` lists the Nemotron model IDs and makes the first live call. See [FEEDBACK.md](FEEDBACK.md).

## How Customs compares

| Capability | Name checkers (Slopstop, SlopGuard) | Customs |
|---|---|---|
| Package name and registry checks | Yes | Yes |
| Repositories and agent skills | No | Yes (GitHub; other hosts ask) |
| Sandbox X-ray of the artifact | No | Static X-ray of install-time code built; sandboxed run on Nebius Serverless Jobs planned |
| Agent-targeted prompt-injection scan | No | Built and wired in; not run live (no Nebius key, see above) |
| Resolves intent and suggests the real package | No | Yes (typo check, seed list) |
| Patches the code and re-runs tests | No | Yes (`customs fix`) |

## Status

Build status and gate checklist: [docs/gate3.md](docs/gate3.md). Running feedback on the Nebius and NVIDIA tools: [FEEDBACK.md](FEEDBACK.md).

## License

MIT. See [LICENSE](LICENSE).
