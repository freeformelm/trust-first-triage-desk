# Demo Script — 3 Minutes

3 minutes = 180 seconds. Every word costs ~0.5 seconds. Practice once with stopwatch.

## Structure (target seconds)

### Hook — 15s
> "Ten thousand Indian healthcare facilities claim ICU, NICU, emergency, oncology. But how many actually deliver? We built the Trust Desk so non-technical planners get evidence, not promises."

### Problem — 25s
- Show kickoff slide stat: 47,169 facilities in FDR, 10k India
- Field coverage chart: equipment 77%, capacity 25% — these are CLAIMS
- "VF Match shows you WHERE the deserts are. We show you WHICH facilities you can trust inside them."

### The Workflow — 90s

**Beat 1 (20s): Triage view**
- Pick capability = `ICU`, state = `Bihar`
- Table appears: 47 facilities claim ICU, status badges: 12 verified, 9 contradicted, 26 unclear
- "Every status is backed by evidence we extracted from the facility's own text."

**Beat 2 (35s): Facility Detail — the wow moment**
- Click a `contradicted` facility
- Header: facility name, district, lat/lng
- Claims table: ICU claim flagged red
- Evidence panel shows the snippet: *"ICU cases are referred to district hospital. No NICU."* — `contradicts` cue word highlighted
- Confidence bar: 38%
- "Without the Trust Desk, this hospital looks ICU-equipped. With it, you see the truth."

**Beat 3 (25s): Planner persists work**
- Add note: "Confirmed via phone — no ICU. Refers to PMCH."
- Click Mark Rejected
- Add to shortlist "Bihar PHC audit"
- "Everything persists in Lakebase Postgres. Tomorrow's planner picks up where today's left off."

**Beat 4 (10s): District context (stretch)**
- Toggle District tab
- NFHS-5 burden bars for Bihar vs verified ICU coverage
- "12 real ICUs for a district with 8% maternal mortality risk. That's the planning surface VF needs."

### Tech credit + close — 30s
- "Built on Databricks Free Edition: Unity Catalog, Delta medallion, Foundation Model APIs for extraction, Lakebase Postgres for planner state, Databricks Apps for the UI. Every score cites the source text. Every uncertainty is shown honestly. Twenty hand-labeled eval scenarios — N/20 correct."
- "Trust-First Triage Desk. Thank you."

### Demo Discipline
- Pre-load the Bihar example. No live LLM calls in the demo — too slow, too fragile.
- Have a second example queued in case Bihar misbehaves.
- Record screen at 1080p, 30fps. Voice-over after the fact if needed.
- 2.5 minute target; leaves 30s slack.

## Pre-Demo Checklist
- [ ] Live app URL working
- [ ] Three facilities pre-bookmarked (one verified, one contradicted, one unclear)
- [ ] Lakebase state cleared (so verifications look fresh)
- [ ] All status badges showing
- [ ] Map/chart in District tab renders
- [ ] Test on laptop battery (Free Edition sometimes spins down)
- [ ] Backup video recorded in case live demo fails on judging day
