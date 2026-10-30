# Message to the organisers (to send before 10:00 PT on 30 October)

Subject: Customs submission: Nebius Token Factory access blocked by country

Hello,

Thank you for the note about my Customs submission. I want to explain why it does not show a live Nebius and NVIDIA run, and ask for your decision.

I am an individual entrant in Liberia. Liberia is not in the country list of the Token Factory billing form, so I could not save billing details or create an API key. I recorded this on 17 October in FEEDBACK.md in the repository.

What is built:
- A Token Factory client (`customs/llm.py`) and Nemotron Nano, Super and Ultra steps for triage and prompt-injection scanning (`customs/llm_checks.py`).
- The checkpoint calls them whenever `NEBIUS_API_KEY` is set (`customs/checkpoint.py`). A model can raise a verdict to INSPECT but never lower one.
- Tests with a fake transport. Nothing in the submission claims a live Nebius or NVIDIA result, and the README says so.

What I am asking:
1. Can you give me a Token Factory key or credits, or confirm the submission stays eligible as it is?
2. If you can, I will run `scripts/gate1_check.py` and the live checkpoint straight away and update the submission before the deadline.

Repository: https://github.com/Mammajam/agent-customs
Demo: https://customs-dashboard-rho.vercel.app

Regards,
Mamadou Kromah
