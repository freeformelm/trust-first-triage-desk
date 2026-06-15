# Databricks Hackathon

## Project Context
DAIS 2026 Databricks Hackathon — Healthcare Facility Intelligence (Virtue Foundation × Databricks Actionable Data Initiative).
- **Edition:** Databricks Free Edition (limited compute, single-node Spark OK, batch LLM calls)
- **Deliverable:** Databricks App (not just notebook); audience = non-technical planner
- **Core requirements:** extract structure · show evidence · communicate uncertainty honestly · persist work
- **Data:** 10,000 India healthcare facility records, 51 cols — output of FDR (Bright Data → GenAI extract → entity resolution)
- **Field coverage (treat noisy fields as CLAIMS to verify):** description 100%, capability 99.7%, procedure 92.5%, equipment 77%, year_established 48%, capacity 25%
- **Supplemental:** India Post PIN Code Directory (165,627 rows), NFHS-5 District Health Indicators (706 districts × 109 cols)
- **Workspace:** `https://dbc-faa88b0d-a49b.cloud.databricks.com`
- **Marketplace listing:** `19326b3d-db63-4627-abc0-cf4e8131a305`
- **Hackathon page:** https://developers.databricks.com/hackathon/
- **Devpost:** https://dais-for-good-2026.devpost.com/  — official name "Databricks Apps & Agents for Good Hackathon 2026"
- **Deadline:** 2026-06-16 @ 2:30pm PDT (HARD)
- **Team size required:** 2 to 4 (solo not allowed)
- **Submission:** Git repo + live Databricks App URL + 3-min demo video
- **Judging:** Product Judgment · Evidence & Uncertainty · Technical Execution · Ambition
- **Non-negotiables:** cite text for every claim/recommendation/score; communicate uncertainty; persist user actions (notes, overrides, shortlists, scenarios, decisions); non-technical user workflow
- **Prizes:** 1st $10k · 2nd $5k · 3rd $2.5k
- **Tracks (pick ONE):** 1. Facility Trust Desk · 2. Medical Desert Planner · 3. Referral Copilot · 4. Data Readiness Desk
- **LOCKED direction:** Track 1 — **Trust-First Triage Desk** (with stretch into Track 2 district context). Frame: Track 1 done well unlocks Tracks 2/3/4 by side effect.
- **Product name:** Trust-First Triage Desk
- **Team:** 2 — Perin Shah (Data Engineer, pshah@dlrgroup.com) + Chialing Wei (Data Scientist). Solo would have been ineligible (Devpost min team size 2).
- **App framework:** Streamlit (faster than AppKit/TS for 24h sprint)
- **LLM endpoint:** `databricks-meta-llama-3-3-70b-instruct` (Foundation Model API, no external keys)
- **Agent onboarding pack:** `AGENT_BRIEF.md` + `agent_briefs/{data_engineer,data_scientist,contracts,prompts}.md`
- **Sponsor's existing product to differentiate from:** VF Match (globe/grid UI, medical desert layers, hospital coverage index, accessibility)

## Data Gotchas
- PIN code directory grain = post office, not pincode → joins on `pincode` fan out, dedupe first
- ~12,600 PIN directory rows have NA lat/lng
- NFHS-5: `*` = suppressed (treat as NULL), `(29.5)` = low-sample estimate (use with caution)
- NFHS-5 col names long & human-readable → snake_case rename on load
- District/state names inconsistent across sources → prefer spatial join (geoBoundaries / DataMeet polygons) over string match

## User
- pshah@dlrgroup.com (DLR Group)

## Environment
- Platform: Windows 11
- Shell: bash (Git Bash) — use Unix shell syntax (forward slashes, `/dev/null`)
- Working dir: `C:\Users\PSHAH\OneDrive - DLR Group\Documents\Github\databricks_hackathon`
- Python: assume venv unless told otherwise

## Stack (planned)
- Databricks SDK / CLI
- PySpark / Delta Lake
- Mosaic AI Agent Framework (`databricks-agents`)
- MLflow for tracking
- Unity Catalog for governance

## Conventions
- Notebooks in `notebooks/`, source modules in `src/`, data in `data/` (gitignored)
- Configuration via env vars or `.env` (never commit secrets)
- Use Databricks workspace paths for cluster-side code, local paths for dev

## Workflow
- Plan in `plan.md` before non-trivial implementation
- Prefer Databricks-native primitives (Delta, Unity Catalog, Jobs) over generic alternatives
- Validate against Databricks runtime version constraints

## TODO (fill in once data/problem known)
- Data source and schema
- Problem statement / scoring criteria
- Cluster config / runtime version
- Workspace URL and target catalog/schema
