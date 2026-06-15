# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Build Bronze + Silver
# MAGIC
# MAGIC Loads facilities into bronze, then builds silver layer:
# MAGIC - `silver_facility` — JSON arrays parsed, India bounding-box validated, state normalized
# MAGIC - `silver_pincode` — deduped to one row per pincode (HO > PO > BO priority)
# MAGIC - `silver_district_health` — NFHS-5 with normalized district/state cols
# MAGIC
# MAGIC Idempotent — safe to re-run.

# COMMAND ----------

import sys, os
repo_root = os.path.abspath(os.path.join(os.getcwd(), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.config import CFG
from src.ingest import run_all_bronze, run_all_silver

# COMMAND ----------

# MAGIC %md ## Ensure target catalog + schema exist

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CFG.catalog}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CFG.catalog}.{CFG.schema}")

# COMMAND ----------

# MAGIC %md ## Bronze

# COMMAND ----------

run_all_bronze(spark)
display(spark.sql(f"SELECT COUNT(*) AS bronze_rows FROM {CFG.fq(CFG.bronze_facility)}"))

# COMMAND ----------

# MAGIC %md ## Silver

# COMMAND ----------

run_all_silver(spark)

# COMMAND ----------

# MAGIC %md ## Sanity checks

# COMMAND ----------

display(spark.sql(f"""
    SELECT
      COUNT(*)                                                 AS total,
      COUNT_IF(has_valid_coords)                               AS valid_coords,
      COUNT_IF(NOT has_valid_coords AND latitude IS NOT NULL)  AS bad_coords_dropped,
      COUNT_IF(SIZE(capabilities)  > 0)                        AS with_capability_array,
      COUNT_IF(SIZE(specialties)   > 0)                        AS with_specialties,
      COUNT_IF(SIZE(equipment)     > 0)                        AS with_equipment_array,
      COUNT_IF(SIZE(source_urls)   > 0)                        AS with_citations
    FROM {CFG.fq(CFG.silver_facility)}
"""))

# COMMAND ----------

# Spot-check the bad-geocoding finding (Sanjivani Hospital, Kerala — coords were Atlantic)
display(spark.sql(f"""
    SELECT facility_id, name, state, latitude, longitude, has_valid_coords
    FROM {CFG.fq(CFG.silver_facility)}
    WHERE LOWER(name) LIKE '%sanjivani%'
"""))

# COMMAND ----------

display(spark.sql(f"""
    SELECT pincode, officename, officetype, district, statename
    FROM {CFG.fq(CFG.silver_pincode)}
    LIMIT 5
"""))

# COMMAND ----------

display(spark.sql(f"""
    SELECT district, state, women_age_15_49_who_are_literate_pct
    FROM {CFG.fq(CFG.silver_district_health)}
    WHERE women_age_15_49_who_are_literate_pct IS NOT NULL
    ORDER BY women_age_15_49_who_are_literate_pct
    LIMIT 5
"""))
