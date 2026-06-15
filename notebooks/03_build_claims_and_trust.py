# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Build silver_claim, silver_evidence, gold_facility_trust
# MAGIC
# MAGIC Baseline classifier (rules-only) from `src/classifier.py`. Chialing will
# MAGIC layer LLM fallback on top, but this produces a working trust score today
# MAGIC so the Streamlit app has something to render.

# COMMAND ----------

import sys, os
repo_root = os.path.abspath(os.path.join(os.getcwd(), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.config import CFG
from src.trust_compute import run_all

# COMMAND ----------

run_all(spark)

# COMMAND ----------

# MAGIC %md ## Sanity checks

# COMMAND ----------

display(spark.sql(f"""
    SELECT capability, COUNT(*) AS claims
    FROM {CFG.fq(CFG.silver_claim)}
    GROUP BY capability
    ORDER BY claims DESC
"""))

# COMMAND ----------

display(spark.sql(f"""
    SELECT capability, status, COUNT(*) AS facilities, ROUND(AVG(trust_score), 3) AS avg_trust
    FROM {CFG.fq(CFG.gold_facility_trust)}
    GROUP BY capability, status
    ORDER BY capability, status
"""))

# COMMAND ----------

# Inspect contradicted ICU claims — these are the demo wow-moments
display(spark.sql(f"""
    SELECT t.facility_id, f.name, f.state, f.city,
           t.claim_count, t.supporting_evidence_count, t.contradicting_evidence_count,
           t.trust_score, t.status
    FROM {CFG.fq(CFG.gold_facility_trust)} t
    JOIN {CFG.fq(CFG.silver_facility)} f USING (facility_id)
    WHERE t.capability = 'icu' AND t.status = 'contradicted'
    LIMIT 20
"""))

# COMMAND ----------

# Inspect verified NICU claims
display(spark.sql(f"""
    SELECT t.facility_id, f.name, f.state, f.city,
           t.claim_count, t.supporting_evidence_count, t.trust_score
    FROM {CFG.fq(CFG.gold_facility_trust)} t
    JOIN {CFG.fq(CFG.silver_facility)} f USING (facility_id)
    WHERE t.capability = 'nicu' AND t.status = 'verified'
    ORDER BY t.trust_score DESC
    LIMIT 10
"""))
