# Demo Script — 3 Minutes

3 minutes = 180 seconds. Practice with stopwatch.

**Live URL:** https://trust-first-triage-desk-108684035875991.aws.databricksapps.com

## Pre-Demo Setup

Pre-pin in browser tabs so you don't fumble live:
- Tab 1: Triage view with `capability = ICU`, `state = Kerala` (or `Maharashtra`)
- Tab 2: Facility Detail with `facility_id` = `5c39dc80-0f8e-4fa1-9f53-fc27fbd2634e` (India Hospital, Thiruvananthapuram — contradicted ICU)
- Tab 3: Facility Detail with a verified NICU example (Wadia Children Hospital Mumbai: `f73e1e8e-f5b0-4d55-9e93-9854283da691`)
- Tab 4: District Context with `state = Madhya Pradesh` (Jhabua = lowest women literacy 38.6%)

## Demo Arc (180s target)

### Hook — 15s
> "Ten thousand Indian healthcare facilities claim ICU, NICU, emergency, oncology. But how many actually deliver? We built the Trust-First Triage Desk so non-technical planners get evidence — not promises."

### The problem — 25s
- Show kickoff stat: 10,088 facilities, capability 99.7% coverage but capacity only 25%
- Key insight: "the noisy fields ARE the claims. The Trust Desk is what tells you which to believe."
- Briefly mention VF Match (sponsor): "VF Match shows you the deserts. Trust Desk tells you which oases are real."

### Workflow walkthrough — 100s

**Beat 1 — Triage list (20s)**
- Switch to Tab 1: ICU in Kerala
- "47 facilities claim ICU. Trust Desk grades them: 12 verified, 9 contradicted, 26 unclear."
- "Every status is backed by a quoted source snippet. We never present weak evidence as fact."

**Beat 2 — Contradiction wow moment (35s)**
- Switch to Tab 2: India Hospital, Thiruvananthapuram (contradicted ICU)
- Expand the ICU panel
- "Facility claims ICU in their capability list."
- Show the evidence panel: green check from `capabilities` field, RED contradiction snippet from `description` — "ICU cases referred to..."
- "Without the Trust Desk this hospital reads ICU-equipped. With it, you see the truth."
- Trust score 0.43, status = contradicted

**Beat 3 — Persisted decision (25s)**
- Add a planner note: "Confirmed via phone — refers to NMC. Update record."
- Click **❌ Reject ICU**
- "Persisted to Lakebase Postgres. Tomorrow's planner picks up where today's left off."
- Flip to **My Work** tab — the verification appears in history.

**Beat 4 — District context (stretch, 20s)**
- Tab 4: Madhya Pradesh district view
- "Women's literacy in Jhabua: 38.6% — lowest in India. NFHS-5 from the Government of India."
- "Pair Trust Desk's verified facility coverage with NFHS-5 burden to see real planning need."

### Tech credit + close — 40s
- "Built end-to-end on Databricks Free Edition: Unity Catalog medallion, Foundation Model APIs for the LLM fallback layer, Lakebase Postgres for planner persistence, Databricks Apps for the UI."
- "Three tiers of extraction: parse JSON-array claims → regex rules across 12 capability classes → LLM fallback for free-text only when rules can't fire."
- "Every score cites the source text. Every uncertainty is shown honestly. Status thresholds require multi-source corroboration."
- "Trust-First Triage Desk — for planners who can't afford to trust promises."

## Demo Discipline
- Pre-load all 4 tabs BEFORE recording — no live LLM calls in the demo
- Record at 1080p, 30fps minimum
- Have backup screen recording ready in case live demo fails on judging day
- Aim for 2:45, leave 15s slack

## Pre-Demo Checklist
- [ ] Live app URL working in incognito (no stale session)
- [ ] India Hospital ICU contradicted shows red snippet
- [ ] Wadia Children NICU shows green supporting evidence
- [ ] Verify/Reject buttons write to Lakebase (test once before recording)
- [ ] My Work tab shows your verifications
- [ ] District tab renders Jhabua at top of low-literacy sort
- [ ] All status badges showing (✅ ⚠️ ❌)
- [ ] Backup video recorded in case live demo fails
