# Feedback on Token Factory, AI Cloud and NVIDIA tools

Running log, kept from day 1 of the build. Each entry says what happened, what it cost, and what would have helped. Entries are dated.

## 2026-10-17

- **Billing country list is short.** The Billing details form (Individual and Company tabs) offers 73 to 74 countries, mostly Europe, North America, parts of Asia and Latin America, plus Egypt, Morocco and South Africa from Africa. Liberia is not listed, so billing cannot be saved for a Liberian entrant. Impact: Gate 1 is blocked on this. Would help: a fuller list, or a documented route for countries not listed.
- **Hackathon and Builder Program sign-up emails arrive separately.** The Builder Program welcome says the $25 Token Factory credit is coming in a separate email, and it arrived as a promo code. Impact: the promo code is easy to miss in a busy inbox. Would help: one email with the credit, or the code shown in the Token Factory dashboard.

## 2026-10-19

- **Docs do not list NVIDIA Nemotron model IDs.** The Token Factory documentation pages I could read name the base URL (`https://api.tokenfactory.nebius.com/v1/`) and bearer auth, but do not list Nemotron Nano, Super or Ultra model IDs. Impact: the code reads model IDs from environment config and expects them from `/v1/models`, so this is a workaround, not a blocker. Would help: a model table with exact IDs and tier names.
- **Token Factory access is confirmed by email, but no API key yet.** The "Welcome to Nebius Token Factory" email arrived on 19 October. Impact: Gate 1 still needs a key from the dashboard. Would help: a note in that email on how to create the first key and what it is billed against.

## 2026-10-30

- **Country not supported, so no key and no live run.** Liberia is not in the Billing details country list, and I could not create a Token Factory API key. Impact: the Nebius client, the Nemotron triage and injection-scan steps, and their wiring into the checkpoint are built and tested only against a fake transport, and an organiser email today flagged the submission as possibly not built with Nebius and NVIDIA. This was the cause of the Gate 1 block on 17 and 19 October. Would help: a documented route for unsupported countries (a hackathon-issued key or credits), and a notice about country limits before sign-up, not at the billing step.
- **Eligibility rules and billing availability differ.** The hackathon rules did not exclude my country, but the platform's billing form does not support it. A line in the rules linking to the supported-country list would have shown this on day 1.
