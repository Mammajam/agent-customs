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

## Development

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](LICENSE).
