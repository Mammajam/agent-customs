# Video script: 2:45 cut (limit is under 3 minutes)

Plan: record on 28 Oct, edit on 28 Oct, upload to YouTube as public. Captions on. Royalty-free or no music. No third-party logos without permission.

| Time | Scene | Voiceover | On screen |
|---|---|---|---|
| 0:00–0:15 | Hook | "AI coding agents install packages that don't exist. Attackers register those names first." | An agent runs `pip install reqeusts` |
| 0:15–0:35 | The problem | "Researchers found 127 package names that frontier models consistently hallucinate. Agents hallucinated 85% of repository names when asked to clone one." | Figures from the plan's sources, each on screen with its source name |
| 0:35–0:55 | Gap in existing tools | "Name checkers check names. They don't cover repositories or skills, they never run what they approve, and they only block." | Comparison table from the README |
| 0:55–1:25 | Customs at work | "Customs sits between the agent and the shell. It blocks the hallucinated name, and suggests the real package." | Hook output in Claude Code: BLOCK, reason, "Did you mean requests?" |
| 1:25–1:55 | The fix loop | "Then it writes the fix, and proves it with the project's tests. If the tests fail, the original file comes back." | `customs fix` run, tests pass, manifest diff on screen |
| 1:55–2:20 | Under the hood | "The checks use public registries and GitHub. Nemotron through Token Factory handles triage, intent and the injection scan, and Tavily handles provenance." | Architecture diagram from the README. Show only the LLM steps that ran live |
| 2:20–2:35 | Measured results | "On our labelled set: 12 of 12 fabricated names caught, no established package falsely blocked, median latency under a second." | Evaluation numbers from the dashboard, with the corpus caveat stated on screen |
| 2:35–2:45 | Close | "Customs. Check before the agent runs." | Repository link and dashboard URL |

## Notes for recording

- Show live results. Do not show numbers from a run you cannot reproduce.
- Say the corpus caveat aloud: the fabricated names do not exist on PyPI, so the test covers that path only.
- If Nemotron or Tavily are not live when recording, say so on screen. Do not show live verdicts that did not come from the live calls.
- The script assumes the LLM steps are live. If they are not, cut the Nemotron and Tavily lines from the voiceover at 1:55–2:20.
