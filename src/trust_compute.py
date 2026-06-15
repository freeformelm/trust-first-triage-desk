"""Build silver_claim, silver_evidence, gold_facility_trust from silver_facility.

Owner: shared (DE wires it, DS refines weights).

Run as a Databricks notebook over silver_facility — produces:
  - hackathon.trust_desk.silver_claim
  - hackathon.trust_desk.silver_evidence
  - hackathon.trust_desk.gold_facility_trust

Free-Edition friendly: all pure Python on the driver since silver_facility is only 10k rows.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.classifier import (
    CAPABILITY_RULES,
    classify_facility,
    find_evidence_for_capability,
)
from src.config import CFG
from src.evidence import status_label, trust_score


def _as_list(v: Any) -> list:
    """Safe list coercion for pandas/numpy values.

    Spark ARRAY<STRING> columns come back as numpy arrays after .toPandas(),
    and `value or []` triggers numpy's ambiguous-truthiness error.
    """
    if v is None:
        return []
    try:
        import numpy as np  # type: ignore
        if isinstance(v, np.ndarray):
            return [x for x in v.tolist() if x is not None]
    except Exception:
        pass
    if isinstance(v, list):
        return [x for x in v if x is not None]
    # Scalar NaN check
    try:
        import pandas as pd  # type: ignore
        if pd.isna(v):
            return []
    except Exception:
        pass
    return [v]

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession


def build_silver_claim_and_evidence(spark: "SparkSession") -> tuple["DataFrame", "DataFrame"]:
    from pyspark.sql import Row

    silver = spark.read.table(CFG.fq(CFG.silver_facility)).toPandas()
    now = datetime.now(timezone.utc)

    claim_rows: list[Row] = []
    evidence_rows: list[Row] = []

    for _, f in silver.iterrows():
        claims = classify_facility(
            facility_id=f["facility_id"],
            capabilities=_as_list(f.get("capabilities")),
            procedures=_as_list(f.get("procedures")),
            equipment=_as_list(f.get("equipment")),
            specialties=_as_list(f.get("specialties")),
        )
        for c in claims:
            claim_rows.append(
                Row(
                    facility_id=c.facility_id,
                    claim_id=c.claim_id,
                    claim_type=c.claim_type,
                    claim_value=c.claim_value,
                    claim_raw=c.claim_raw,
                    source_field=c.source_field,
                    source_text_span=c.source_text_span,
                    extraction_confidence=c.extraction_confidence,
                    llm_model="rules-v1",
                    extracted_at=now,
                )
            )

        # Evidence: scan all text fields for each unique capability claimed by this facility
        unique_caps = {c.claim_value for c in claims}
        desc = f.get("description")
        try:
            import pandas as pd  # type: ignore
            if pd.isna(desc):
                desc = None
        except Exception:
            pass
        text_by_field = {
            "description": desc,
            "capabilities": _as_list(f.get("capabilities")),
            "procedures": _as_list(f.get("procedures")),
            "equipment": _as_list(f.get("equipment")),
            "specialties": _as_list(f.get("specialties")),
        }
        for cap in unique_caps:
            # Use the highest-confidence claim_id for this (facility, capability) pair
            cap_claims = [c for c in claims if c.claim_value == cap]
            primary = max(cap_claims, key=lambda c: c.extraction_confidence)
            for ev in find_evidence_for_capability(primary.claim_id, cap, text_by_field):
                evidence_rows.append(
                    Row(
                        evidence_id=ev.evidence_id,
                        claim_id=ev.claim_id,
                        snippet=ev.snippet,
                        source_field=ev.source_field,
                        polarity=ev.polarity,
                        retrieval_score=ev.retrieval_score,
                    )
                )

    silver_claim_df = spark.createDataFrame(claim_rows) if claim_rows else spark.createDataFrame(
        [], schema="facility_id string, claim_id string, claim_type string, claim_value string, "
                   "claim_raw string, source_field string, source_text_span string, "
                   "extraction_confidence double, llm_model string, extracted_at timestamp"
    )
    silver_evidence_df = spark.createDataFrame(evidence_rows) if evidence_rows else spark.createDataFrame(
        [], schema="evidence_id string, claim_id string, snippet string, source_field string, "
                   "polarity string, retrieval_score double"
    )

    silver_claim_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        CFG.fq(CFG.silver_claim)
    )
    silver_evidence_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        CFG.fq(CFG.silver_evidence)
    )
    return silver_claim_df, silver_evidence_df


def build_gold_facility_trust(spark: "SparkSession") -> "DataFrame":
    """Aggregate to one row per (facility, capability) with trust score + status."""
    spark.read.table(CFG.fq(CFG.silver_claim)).createOrReplaceTempView("_sc")
    spark.read.table(CFG.fq(CFG.silver_evidence)).createOrReplaceTempView("_se")

    agg = spark.sql(
        f"""
        WITH per_cap_claim AS (
          SELECT
            facility_id,
            claim_value AS capability,
            COUNT(*)                                AS claim_count,
            MAX(extraction_confidence)              AS top_extraction_conf,
            COLLECT_SET(claim_id)                   AS claim_ids
          FROM _sc
          GROUP BY facility_id, claim_value
        ),
        per_cap_evidence AS (
          SELECT
            c.facility_id,
            c.capability,
            SUM(CASE WHEN e.polarity = 'supports' THEN 1 ELSE 0 END)     AS supports_n,
            SUM(CASE WHEN e.polarity = 'contradicts' THEN 1 ELSE 0 END) AS contradicts_n
          FROM per_cap_claim c
          LEFT JOIN _se e
            ON ARRAY_CONTAINS(c.claim_ids, e.claim_id)
          GROUP BY c.facility_id, c.capability
        )
        SELECT
          pc.facility_id,
          pc.capability,
          pc.claim_count,
          COALESCE(pe.supports_n, 0)     AS supporting_evidence_count,
          COALESCE(pe.contradicts_n, 0) AS contradicting_evidence_count,
          pc.top_extraction_conf
        FROM per_cap_claim pc
        LEFT JOIN per_cap_evidence pe
          ON pe.facility_id = pc.facility_id AND pe.capability = pc.capability
        """
    ).toPandas()

    # Apply Python trust_score + status_label (single source of truth lives in src/evidence.py)
    from pyspark.sql import Row

    rows: list[Row] = []
    now = datetime.now(timezone.utc)
    for _, r in agg.iterrows():
        ts = trust_score(
            claim_count=int(r["claim_count"]),
            supports=int(r["supporting_evidence_count"]),
            contradicts=int(r["contradicting_evidence_count"]),
            extraction_conf=float(r["top_extraction_conf"]),
        )
        st = status_label(
            trust=ts,
            supports=int(r["supporting_evidence_count"]),
            contradicts=int(r["contradicting_evidence_count"]),
        )
        rows.append(
            Row(
                facility_id=r["facility_id"],
                capability=r["capability"],
                claim_count=int(r["claim_count"]),
                supporting_evidence_count=int(r["supporting_evidence_count"]),
                contradicting_evidence_count=int(r["contradicting_evidence_count"]),
                trust_score=float(ts),
                status=st,
                last_computed_at=now,
            )
        )

    gold = spark.createDataFrame(rows) if rows else spark.createDataFrame(
        [], schema="facility_id string, capability string, claim_count int, "
                   "supporting_evidence_count int, contradicting_evidence_count int, "
                   "trust_score double, status string, last_computed_at timestamp"
    )
    gold.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        CFG.fq(CFG.gold_facility_trust)
    )
    return gold


def run_all(spark: "SparkSession") -> None:
    build_silver_claim_and_evidence(spark)
    build_gold_facility_trust(spark)
