# Customs

**Customs is a dependency checkpoint for coding agents. It checks every package install, repository clone and skill fetch before anything runs, and fixes the agent's code when it blocks a hallucinated name.**

Track: Coding & Agentic Engineering

## The problem

AI coding agents install software on their own, and they often install things that don't exist. Researchers found 127 package names that every major frontier model consistently hallucinated. Agents hallucinated 85% of repository names when asked to clone one, and 100% of skill names when asked to install a skill. Attackers register these names first. The fake npm package react-codeshift spread into 237 GitHub repositories.

## How it works

1. **Declare.** Customs parses the command the agent is about to run: pip, npm, git clone, and skill installs.
2. **Inspect.** It checks the registries and GitHub: whether the name exists, its age, downloads or stars, advisories for the pinned version, and how close the name is to a popular package.
3. **Decide.** Each item is CLEAR, INSPECT (the developer approves) or BLOCK (the agent is refused, with the reason and the suggested real name).
4. **Fix.** `customs fix` replaces the blocked name in the manifest, checks the suggestion again at the pinned version, and runs the project's tests. If the tests fail, the original file comes back.

Customs runs inside Claude Code as a PreToolUse hook, and as an MCP server, and as a GitHub Action on pull requests.

## Built with

Python (standard library only), the Nebius Token Factory API, NVIDIA Nemotron models, Tavily search, the PyPI, npm, OSV and GitHub public APIs, Claude Code hooks, and the Model Context Protocol.

## How we use Nebius and NVIDIA

- **Token Factory** is the model endpoint for the LLM steps. Nemotron Nano is for triage of suspicious installs, Nemotron Super for resolving the intended package, and Nemotron Ultra for scanning READMEs and install scripts for prompt injection. The code for all three is built. Live calls are the next step, and this paragraph will be updated with the measured results once they run.
- **Serverless Jobs** is planned for the sandboxed install (X-ray), so untrusted packages never run on the developer's machine.
- **The dashboard** is planned to run on a Serverless Endpoint with scale-to-zero, so judges can try a package.

## Results

The checkpoint (name, registry, GitHub and advisory checks) is measured on a labelled set of 22 install commands: 12 of 12 fabricated package names were caught, and 0 of 10 established packages were falsely blocked. Median check latency is about 0.7 seconds, and p95 is about 3.3 seconds, which includes the static X-ray downloads. The set is small, and the fabricated names are ones that do not exist, so it measures that path only. These results come from the checkpoint without the LLM steps. We say so in the video and the README.

Sources for the problem figures: CSA Research Note on HalluSquatting; Sonar, AI code verification debt; Slopstop on PyPI; SlopGuard's detection write-up.

## What's next

Sandboxed X-ray of packages on Serverless Jobs, and an allowlist and approval flow for teams.
