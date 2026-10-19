# Submission checklist: Official Rules requirements

Status is as of 19 October. "Done" means built and checked in this repo. "Planned" means not yet done. "At risk" means a blocker is open. The 16 requirements are those in the project plan's compliance matrix.

| # | Requirement | How Customs meets it | Status |
|---|---|---|---|
| 1 | Runtime call to the Token Factory inference API, or runs on Nebius AI Cloud | `customs/llm.py` and `customs/llm_checks.py` call Token Factory. The dashboard is ready for a Nebius Serverless Endpoint | Planned: live calls wait on the API key (Gate 1) |
| 2 | Uses at least one NVIDIA open-source model | Nemotron Nano (triage), Super (intent resolution), Ultra (injection scan), read from config | Planned: model IDs confirmed from `/v1/models` once the key exists |
| 3 | Genuine attempt at the track goal (Stage One pass/fail) | `customs fix` writes the patch and runs the tests, rolling back on failure. The checkpoint runs inside Claude Code as a PreToolUse hook | Done for the checkpoint and fix loop. Judged at Stage One on the video and write-up |
| 4 | Working demo URL, free to test until judging ends (15 Dec) | `customs/web.py` dashboard and `Dockerfile` with a try-a-package box | At risk: no public host yet |
| 5 | Public GitHub repo, OSI license visible in the About section | github.com/Mammajam/agent-customs, MIT license committed | Done for the license. Confirm the About panel shows MIT |
| 6 | README with setup steps, plus how Nemotron, Token Factory and Nebius services are used | `README.md`, with the "How we use Nebius and NVIDIA" section and architecture | Done in draft. Update once the live calls run |
| 7 | Video under 3 minutes, public on YouTube, project shown working | Script in `docs/video-script.md` | Planned: recording and YouTube upload are yours |
| 8 | Text description of features and functionality | `docs/devpost.md` draft | Planned: draft ready, to be reviewed before submitting |
| 9 | Track named on the submission | Coding & Agentic Engineering | Planned: enter on the Devpost form |
| 10 | Feedback on Token Factory, AI Cloud and NVIDIA tools | `FEEDBACK.md`, running log since 17 Oct | Done (running). Also eligible for Most Valuable Feedback |
| 11 | Project new, or significantly updated after 26 Aug | Repository created 17 Oct 2026 | Done |
| 12 | Authorised use of third-party APIs | PyPI, npm, OSV, GitHub and Tavily public APIs. Backoff on failure: a failed lookup asks, never passes | Done for the public APIs. Tavily live use is planned |
| 13 | Open-source components extended, licences respected | MIT and Apache dependencies only. Detection logic written from scratch, not a fork of SlopGuard | Done. Confirm before submitting |
| 14 | Materials in English | All materials in English | Done |
| 15 | Entrant eligibility | Individual entrant. Liberia is not on the excluded list | Done (confirmed in the plan) |
| 16 | Best Use of Tavily bonus: a functional runtime call | Tavily provenance lookup on every suspicious name, in `customs/llm_checks.py` | Planned: needs a Tavily key |

## Open items before submitting

1. Token Factory API key, then run `scripts/gate1_check.py` and set the Nemotron model IDs.
2. Tavily API key, then run one live provenance call.
3. A public host for the dashboard, serving the demo URL until 15 Dec.
4. Record and upload the video, then paste its YouTube link into the Devpost form.
5. Review and submit `docs/devpost.md`.
