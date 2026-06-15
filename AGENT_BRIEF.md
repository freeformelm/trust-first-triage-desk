# AGENT BRIEF — Trust-First Triage Desk

**You are an AI coding agent joining a 2-person hackathon team.** Read this file first, then jump to your role-specific brief.

## TL;DR
- **What:** A Databricks App that lets a non-technical health planner verify which Indian healthcare facilities can actually do what they claim (ICU, maternity, NICU, oncology, trauma, emergency + extended: surgery, cardiology, dialysis, radiology, pediatrics, ophthalmology).
- **Why:** 10,088 messy facility records from the Foundational Data Refresh (FDR) pipeline. Capability/equipment fields are CLAIMS, not facts. Planners need evidence + uncertainty.
- **Hackathon:** Databricks Apps & Agents for Good 2026 (Devpost: https://dais-for-good-2026.devpost.com/)
- **Deadline:** 2026-06-16 @ 2:30pm PDT
- **Deliverable:** Live Databricks App on Free Edition + Git repo + 3-min demo video
- **Track:** Track 1 — Facility Trust Desk (with stretch into Track 2 district context)
- **Stack:** Databricks Free Edition · Unity Catalog · Delta · Lakebase Postgres · Databricks Apps (Streamlit) · Foundation Model APIs (`databricks-meta-llama-3-3-70b-instruct`)
- **LIVE:** https://trust-first-triage-desk-108684035875991.aws.databricksapps.com

## Non-Negotiable App Behaviors (Devpost rules, will fail submission if missing)
1. **Cite text** for every important claim/recommendation/score/ranking
2. **Communicate uncertainty** — no presenting weak evidence as fact
3. **Persist user actions** — notes, overrides, shortlists, verifications must save
4. **Non-technical user workflow** — no SQL or notebook UI; clean, guided experience

## Judging Criteria
1. **Product Judgment** — clear user, thoughtful workflow & tradeoffs
2. **Evidence & Uncertainty** — outputs grounded in citations; uncertainty handled honestly
3. **Technical Execution** — live-demo reliability + effective Databricks use
4. **Ambition** — meaningful work beyond minimum

## Team
- **Data Engineer (DE) — Perin Shah.** Ingest, Delta, Lakebase, App deploy. Owns `src/ingest.py`, `src/lakebase.py`, `app/`.
- **Data Scientist (DS) — Chialing Wei.** Claim extraction, evidence linking, trust score, eval. Owns `src/claims.py`, `src/evidence.py`, `eval/`.

## Where to Read Next
- Role-specific:
  - `agent_briefs/data_engineer.md` — if you support the DE
  - `agent_briefs/data_scientist.md` — if you support the DS
- Shared:
  - `agent_briefs/contracts.md` — table schemas + handoff contracts (single source of truth)
  - `agent_briefs/prompts.md` — LLM prompt templates with examples
  - `plan.md` — phased timeline + risks
  - `team.md` — handoff schedule + sync points
  - `notes.md` — data quirks (add to this as you learn)
  - `runbook.md` — CLI commands (auth, deploy, etc.)
  - `demo_script.md` — 3-min demo script template

## House Rules
1. **No new files in repo root** without checking AGENT_BRIEF first — extend an existing file.
2. **Always honor contracts in `agent_briefs/contracts.md`.** If a column needs to change, update the contract file in the SAME commit.
3. **No deletes during sprint.** If something is wrong, comment + warn — humans decide.
4. **Persist what you change.** New schema → update `src/lakebase.py` SCHEMA_SQL. New table → update `src/config.py`.
5. **Free Edition mindset:** single-node Spark OK, batch + cache LLM calls, no expensive operations on hot paths.
6. **Cite or die:** every output the user sees that summarizes a claim MUST link back to the source snippet/field. If you don't have the citation, don't show the output.

## Source of Truth for Decisions
`plan.md` "Decisions Log" section. Append; never rewrite history.
