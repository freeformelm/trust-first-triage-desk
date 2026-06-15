# Plan — Healthcare Facility Intelligence (DAIS 2026)

## Status
**LIVE.** Building **Trust-First Triage Desk** (Track 1, with stretch Track 2 district context).
- ✓ Scaffolding · ✓ Source schema confirmed · ✓ Silver-layer Delta tables built (10,088 facilities, 9,964 valid coords)
- ✓ Lakebase Postgres provisioned + schema initialized (verifications, annotations, shortlists, saved_searches, claim_embeddings)
- ✓ Claim classifier (12 capabilities, three-tier: parse → rules → optional LLM fallback)
- ✓ silver_claim · silver_evidence · gold_facility_trust populated
- ✓ App deployed: https://trust-first-triage-desk-108684035875991.aws.databricksapps.com

**Remaining (before deadline 2026-06-16 14:30 PDT):**
- Grant app service principal permissions on SQL warehouse + Lakebase Postgres role
- Verify Triage tab renders + verify/reject buttons persist to Lakebase
- Capture screenshot of contradicted ICU example (India Hospital, Kerala / Kamala Nehru, Pune)
- Record 3-min demo video
- Submit Devpost

## ⚠ HARD CONSTRAINTS (Devpost)
- **Deadline:** 2026-06-16 @ 2:30pm PDT (~24h from now — today is 2026-06-15)
- **Team size:** 2 to 4 members required (solo not allowed)
- **Eligibility:** accepted DAIS attendees, of legal age
- **Must submit:** Git repo + live Databricks App URL + 3-min demo video
- **Must run on:** Databricks Free Edition
- **Must use:** provided 10k India facility dataset
- **Prizes:** 1st $10k · 2nd $5k · 3rd $2.5k

## Judging Criteria (Devpost, no weights given)
1. **Product Judgment** — clear user, thoughtful workflow & tradeoffs
2. **Evidence & Uncertainty** — outputs grounded in citations; uncertainty handled honestly
3. **Technical Execution** — live-demo reliability + effective Databricks use
4. **Ambition** — meaningful work beyond minimum

## Non-Negotiable App Behaviors (Devpost rules)
- Non-technical user workflow
- Cite underlying facility text for every important claim/recommendation/score/ranking
- Communicate uncertainty (no presenting weak evidence as fact)
- Persist user actions: notes, overrides, shortlists, scenarios, review decisions

## Hackathon Brief
- **Title:** Healthcare Facility Intelligence on Databricks Free Edition
- **Sponsor:** Virtue Foundation × Databricks (Actionable Data Initiative)
- **Tagline:** Turn 10,000 messy Indian healthcare facility records into decisions planners can trust
- **Hackathon page:** https://developers.databricks.com/hackathon/
- **Edition:** Databricks Free Edition (limited compute)
- **Deliverable:** Databricks App (not just notebook)
- **Audience:** non-technical planner
- **Core requirements:** extract structure · show evidence · communicate uncertainty honestly · persist work

## Data
- 10,000 India healthcare facility records, 51 columns
- Pipeline: Bright Data crawl → GenAI extraction → entity resolution → FDR
- Field coverage (treat noisy fields as CLAIMS to verify, not ground truth):
  - description: 100%
  - capability: 99.7%
  - procedure: 92.5%
  - equipment: 77%
  - year_established: 48%
  - capacity: 25%
- Supplemental: India Post PIN Code Directory (165,627 rows), NFHS-5 (706 districts × 109 indicators)
- Source listing: Databricks Marketplace `19326b3d-db63-4627-abc0-cf4e8131a305` (free)

## Tracks Available (pick ONE)
1. **Facility Trust Desk** — Can a facility actually do what it claims? ← **RECOMMENDED**
2. Medical Desert Planner — Where are real, highest-risk gaps in care? (Overlaps VF Match — sponsor's existing product)
3. Referral Copilot — Where should a patient or coordinator go?
4. Data Readiness Desk — What must be fixed before planning can trust it?

## Existing Sponsor Product to Differentiate From
**VF Match** (vfmatch.org-style): globe + grid UI, medical desert layers, hospital coverage index, hospital accessibility, physician density, volunteer-opportunity discovery. Geographic discovery is solved. Capability verification is not.

## Why Track 1 (Facility Trust Desk)
- Tackles the noisiest, most differentiated part of the dataset (claims vs evidence)
- Maps directly to "communicate uncertainty honestly"
- No overlap with VF Match's geographic discovery
- Free-Edition-friendly: per-facility LLM calls are batched, cached, small surface
- Lakebase fits naturally: planner verification queue, annotations, saved searches
- Demo is crisp: enter facility → ranked claims with evidence snippets + confidence + contradictions → planner verifies → persists

## Architecture (Track 1)

### Data layer (Delta + small)
- `bronze_facility` — raw 10k FDR records as-is
- `silver_facility` — cleaned, normalized district/state names, snake_case
- `silver_claim` — one row per (facility_id, claim_type, claim_value) extracted from capability/procedure/equipment fields
- `silver_evidence` — one row per (claim_id, snippet, source_url, confidence) from description text
- `gold_facility_trust` — facility-level rollup with weighted trust score, evidence count, contradiction count
- `dim_pincode` (deduped India Post lookup)
- `dim_district_health` (NFHS-5 snake_cased, NULL-cleaned)

### Lakebase (planner state)
- `verifications(facility_id, claim_id, planner_id, status, notes, ts)` — manual sign-off
- `saved_searches(planner_id, query, filters, ts)`
- `annotations(facility_id, planner_id, note, ts)`
- pgvector: per-claim embeddings for "find similar claims across facilities"

### App (Databricks App, AppKit/TypeScript or Streamlit)
- **Search:** facility lookup by name / district / claimed capability
- **Trust Desk view:** facility header → claims table with confidence bars → expand to evidence snippets → contradiction flags → planner verify/reject buttons → free-text notes
- **Map sidebar:** district context from NFHS-5 (burden indicators), facility location on PIN polygon
- **Bulk mode:** queue of low-confidence claims to triage
- **Honest UX:** every number is annotated with provenance (`extracted`, `inferred`, `verified`, `contradicted`)

### Agent layer (optional, Phase 4 stretch)
- Mosaic AI agent with tools: `extract_claims(facility_id)`, `find_evidence(claim_id)`, `compare_facilities(ids)`, `district_context(district)`. Genie space fallback over silver_facility.

## Phases

### Phase 0 — Setup (today)
- [ ] `databricks aitools version` check
- [ ] Install Databricks CLI 1.0.0+; `databricks auth login` to Free Edition workspace
- [ ] Confirm workspace URL, catalog, schema
- [ ] Install Virtue Foundation marketplace listing
- [ ] Repo: `notebooks/`, `src/`, `tests/`, `data/` (gitignored), `app/` (Databricks App), `.gitignore`
- [ ] Confirm Track 1 choice with user

### Phase 1 — Ingest & profile
- [ ] Load FDR 10k → `bronze_facility`
- [ ] Profile: field coverage, top capabilities, top procedures, top equipment, district distribution
- [ ] Load PIN directory + NFHS-5; rename to snake_case; NULL-clean `*` and `(x)` patterns
- [ ] Spatial join facility (lat,lng) → district polygon (geoBoundaries / DataMeet); fallback to pincode lookup
- [ ] Document quirks in `notes.md`

### Phase 2 — Claim extraction
- [ ] Define claim taxonomy (capability, procedure, equipment categories)
- [ ] LLM prompt: extract structured claims from free-text description + capability/procedure/equipment fields
- [ ] Output `silver_claim` with raw_text, normalized_value, source_field, extraction_confidence
- [ ] Batch + cache LLM responses (Free Edition cost guard)

### Phase 3 — Evidence linking & trust scoring
- [ ] For each claim, retrieve supporting/contradicting snippets from facility's own description text (and optionally cross-facility)
- [ ] Per-claim confidence = f(extraction_conf, evidence_count, contradictions, field_coverage_prior)
- [ ] Facility-level trust score = weighted aggregate
- [ ] Surface "needs verification" queue (high-impact claims with low confidence)

### Phase 4 — App
- [ ] Scaffold Databricks App (AppKit + TypeScript, or Streamlit)
- [ ] Lakebase provisioning + schema (verifications, saved_searches, annotations, pgvector)
- [ ] Search + Trust Desk views
- [ ] Planner verify/reject + notes → Lakebase
- [ ] Map sidebar with NFHS-5 district context
- [ ] Polished UI (shadcn/ui + Tailwind, Databricks palette per AppKit defaults if TS route)

### Phase 5 — Eval & demo
- [ ] Hand-build 20 verification scenarios; measure trust-score correlation with ground truth
- [ ] MLflow logging of LLM extraction runs
- [ ] Demo script: 4-minute walkthrough (planner persona)
- [ ] Slides / 1-pager summary

## Open Questions (will ask one at a time when user resumes)
- Workspace URL + catalog/schema confirmed?
- Free Edition compute caps / LLM endpoint available?
- Team size + submission deadline?
- Streamlit vs AppKit/TypeScript Databricks App?
- Hard commit to Track 1 or want to discuss Tracks 2/3/4 first?

## Decisions Log
- 2026-06-15: Hackathon = Healthcare Facility Intelligence, Free Edition, Databricks App deliverable
- 2026-06-15: Recommended Track 1 (Facility Trust Desk) over Tracks 2-4 — see "Why Track 1"
- 2026-06-15: LOCKED — Trust-First Triage Desk (Track 1, with stretch Track 2 district context)
- 2026-06-15: Team Perin Shah (DE) + Chialing Wei (DS) registered
- 2026-06-15: Public repo created — https://github.com/freeformelm/trust-first-triage-desk
- 2026-06-15: Lakebase `trust_desk` instance provisioned
- 2026-06-15: EDA confirmed — 10,088 facilities (99% with coords), 706 NFHS districts, 165,627 pincode rows (93% with coords)
- 2026-06-15: India bounding-box filter — dropped 6 facilities with geocoding errors (e.g. Sanjivani Kerala coords in Atlantic)
- 2026-06-15: Status thresholds tightened — `verified` requires ≥2 corroborating sources; `contradicted` triggers on referral-out language (broader pattern: before+after match)
- 2026-06-15: Chialing extended taxonomy from 6 to 12 capabilities (added surgery, cardiology, dialysis, radiology, pediatrics, ophthalmology) + Tier-3 LLM fallback wired
- 2026-06-15: App live at https://trust-first-triage-desk-108684035875991.aws.databricksapps.com

## Risks
- Free Edition compute / LLM quota — batch + cache aggressively
- Claim extraction quality on noisy descriptions — eval set must catch regressions
- Pincode join fan-out (grain = post office, not pincode) — dedupe first
- NFHS-5 `*` suppressed and `(x)` low-sample values misread as numeric — strict NULL casting
- VF Match overlap risk if scope drifts toward Track 2 — stay on capability verification
- 10k rows fit single-node; do NOT over-engineer Spark
