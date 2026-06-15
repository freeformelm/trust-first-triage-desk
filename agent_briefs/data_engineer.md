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

## Order of Operations
1. `databricks auth login --profile databricks_hackathon` (token currently expired)
2. `databricks current-user me` — confirm identity
3. Create catalog + schema:
   - `CREATE CATALOG IF NOT EXISTS hackathon;`
   - `CREATE SCHEMA IF NOT EXISTS hackathon.trust_desk;`
4. Install Virtue Foundation Marketplace listing (ID `19326b3d-db63-4627-abc0-cf4e8131a305`) into `hackathon.trust_desk`
5. Run `src/ingest.py` against marketplace facility table → `bronze_facility` → `silver_facility`
6. Provision Lakebase database; run `src/lakebase.py::init_schema`
7. Scaffold Streamlit app locally; wire to silver_facility + Lakebase
8. `databricks apps deploy` and verify live URL
9. Once DS has populated `silver_claim`, `silver_evidence`, `gold_facility_trust` → wire app to them
10. Demo dry-run × 2, then record 3-min video

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
