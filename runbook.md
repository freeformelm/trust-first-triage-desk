# Runbook — Data Engineer Commands

All commands assume working directory = repo root and Git Bash on Windows.

## Auth (token currently expired)
```bash
databricks auth login --profile databricks_hackathon
databricks current-user me --profile databricks_hackathon
```

## Create catalog + schema
```bash
databricks sql query --profile databricks_hackathon -q \
  "CREATE CATALOG IF NOT EXISTS hackathon;
   CREATE SCHEMA IF NOT EXISTS hackathon.trust_desk;"
```

## Install Marketplace listing
Web UI is faster: Marketplace → search "Virtue Foundation" → Get Instant Access → install into `hackathon.trust_desk`. Listing ID `19326b3d-db63-4627-abc0-cf4e8131a305`.

## Ingest
Run `src/ingest.py` as a Databricks notebook (paste cells) or as a job. For Free Edition single-node:
```python
from src.ingest import load_fdr_to_bronze, bronze_to_silver_facility
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
load_fdr_to_bronze(spark, "hackathon.trust_desk.<marketplace_table_name>")
bronze_to_silver_facility(spark)
```

## Provision Lakebase
Web UI: Compute → Database Instances → Create Database Instance (project `trust_desk`). Wait ~5 min for endpoint.

Export connection values:
```bash
export LAKEBASE_HOST="<endpoint>.cloud.databricks.com"
export LAKEBASE_DB="trust_desk"
export LAKEBASE_USER="<oauth-username>"
```

Init schema:
```python
from sqlalchemy import create_engine
from src.lakebase import init_schema
from src.config import CFG

engine = create_engine(f"postgresql+psycopg://{CFG.lakebase_user}@{CFG.lakebase_host}/{CFG.lakebase_db}")
init_schema(engine)
```

## Local Streamlit (dev loop)
```bash
pip install -r requirements.txt
streamlit run app/app.py
```

## Deploy as Databricks App
```bash
cd app
databricks apps create trust-first-triage-desk --profile databricks_hackathon
databricks apps deploy trust-first-triage-desk --source-code-path . --profile databricks_hackathon
databricks apps logs trust-first-triage-desk --profile databricks_hackathon
```

App URL appears in `databricks apps list` output.

## Common Issues
| Symptom | Fix |
|---------|-----|
| `Valid: NO` on profile | Re-run `databricks auth login --profile databricks_hackathon` |
| Catalog permission denied | Workspace admin must grant USE CATALOG on `hackathon` |
| Marketplace listing not visible | Confirm Free Edition workspace can access the Marketplace |
| LLM endpoint 404 | Check `databricks serving-endpoints list` — endpoint name may differ on Free Edition |
| App fails to start | `databricks apps logs <name>` — usually env-var or import error |
| psycopg can't connect | Lakebase OAuth token refresh — see Databricks Lakebase auth docs |
