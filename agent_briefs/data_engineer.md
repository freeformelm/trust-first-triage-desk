# Agent Brief — Data Engineer Side

**You are supporting the Data Engineer.** They own the data pipeline, Lakebase, and Databricks App deployment.

Read `../AGENT_BRIEF.md` first for project context.

## Your Scope
- Workspace setup: catalog, schema, marketplace listing install
- Bronze → Silver → Gold Delta tables (see `contracts.md`)
- Spatial join: facility lat/lng → district polygon
- Lakebase provisioning + schema migration
- Streamlit app shell wiring (data fetch from Delta via SQL Connector; persistence to Lakebase via psycopg)
- Databricks App deployment + verification
- Demo recording + Git polish

## Out of Scope (do NOT touch)
- `src/claims.py` (DS owns)
- `src/evidence.py` (DS owns — except calling the score function from app)
- `eval/` (DS owns)
- Prompt files (DS owns)

## Order of Operations (status as of 2026-06-15)
1. ✓ `databricks auth login --profile databricks_hackathon`
2. ✓ Created catalog + schema `hackathon.trust_desk`
3. ✓ Virtue Foundation Marketplace listing installed → tables at `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.{facilities, india_post_pincode_directory, nfhs_5_district_health_indicators}`
4. ✓ `notebooks/02_build_silver.py` → bronze_facility, silver_facility, silver_pincode, silver_district_health
5. ✓ `notebooks/03_build_claims_and_trust.py` → silver_claim, silver_evidence, gold_facility_trust
6. ✓ Lakebase provisioned (`ep-solitary-shape-d8czihec`, db `databricks_postgres`)
7. ✓ Schema init: `python scripts/init_lakebase.py`
8. ✓ Workspace sync: `MSYS_NO_PATHCONV=1 databricks sync . /Workspace/Users/freeformelm@gmail.com/trust-first-triage-desk-app --full --exclude ".env" --exclude ".git/*" --exclude "data/*" --profile databricks_hackathon`
9. ✓ App deploy: `databricks apps deploy trust-first-triage-desk --source-code-path /Workspace/Users/freeformelm@gmail.com/trust-first-triage-desk-app --profile databricks_hackathon`
10. ✓ Live URL: https://trust-first-triage-desk-108684035875991.aws.databricksapps.com

**Remaining:**
- [ ] Grant app service principal permissions on SQL warehouse + Lakebase Postgres role
- [ ] Smoke test Triage tab in browser
- [ ] Demo dry-run × 2
- [ ] Record 3-min video

## Key Files You Own
- `src/config.py` (catalog/schema names)
- `src/ingest.py`
- `src/lakebase.py`
- `app/app.py`
- `app/app.yaml`
- `runbook.md`

## App Routes (Streamlit tabs)
| Tab | Reads from | Writes to |
|-----|-----------|-----------|
| Triage | `gold_facility_trust`, `silver_facility` | – |
| Facility Detail | `silver_facility`, `silver_claim`, `silver_evidence` | Lakebase `verifications`, `annotations` |
| District Context (stretch) | `silver_district_health`, `silver_facility` | Lakebase `saved_searches` |
| My Work | Lakebase all tables | – |

## Free Edition Gotchas
- Single-node compute — no big-cluster shuffles
- Foundation Model APIs have rate limits → DS handles, but persist cached extractions in Delta so re-runs are free
- Lakebase is required for "persist user actions" — do NOT use Delta for planner state (no row-level upserts the way Postgres handles them)
- App can read Delta via Databricks SQL Connector; cluster start time is the variable — prefer Serverless SQL Warehouse

## If You Run Into Trouble
- Stale token: `databricks auth login --profile databricks_hackathon`
- Marketplace install fails: check workspace metastore + UC permissions
- Lakebase provisioning slow (~5 min): start it FIRST, run ingest in parallel
- App deploy 4xx: check `app.yaml` env names exactly match secrets in workspace
- Logs: `databricks apps logs <app-name>`
