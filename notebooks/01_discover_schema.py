# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Discover Schema
# MAGIC
# MAGIC Print column names + sample row for each Marketplace source table.
# MAGIC Output of this notebook tells us the exact column names so we can finish
# MAGIC `src/ingest.py::build_silver_*` and `agent_briefs/contracts.md`.
# MAGIC
# MAGIC **Run this first.** Don't load bronze yet.

# COMMAND ----------

import sys
import os

# Ensure src/ is importable when notebook lives in notebooks/
repo_root = os.path.abspath(os.path.join(os.getcwd(), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.config import CFG
from src.ingest import describe_sources, sample_facility

# COMMAND ----------

describe_sources(spark)

# COMMAND ----------

# Inspect one full facility row — paste the result into chat so we can
# confirm the column → silver mapping.
display(sample_facility(spark, n=3))

# COMMAND ----------

# Quick coverage sanity checks against EDA findings
display(spark.sql(f"""
    SELECT
      COUNT(*) AS total_rows,
      COUNT_IF(latitude IS NOT NULL AND longitude IS NOT NULL) AS with_coords
    FROM {CFG.source_facilities}
"""))

# COMMAND ----------

display(spark.sql(f"""
    SELECT address_stateOrRegion, COUNT(*) AS facility_count
    FROM {CFG.source_facilities}
    GROUP BY address_stateOrRegion
    ORDER BY facility_count DESC
    LIMIT 10
"""))
