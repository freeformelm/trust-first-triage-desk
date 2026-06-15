"""Bronze + Silver ingest for FDR facility data + supplementals.

Owner: Data Engineer.
Run as a Databricks notebook or job. Single-node Spark is fine — 10,088 rows.

Source (read-only, from Databricks Marketplace listing
`19326b3d-db63-4627-abc0-cf4e8131a305`):
  - databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities
  - ...india_post_pincode_directory
  - ...nfhs_5_district_health_indicators

Target (writable):
  - hackathon.trust_desk.*  (override via UC_CATALOG / UC_SCHEMA env vars)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.config import CFG

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession


# ---------------------------------------------------------------------------
# Discovery helpers — run these FIRST so we know the exact column names
# ---------------------------------------------------------------------------


def describe_sources(spark: "SparkSession") -> None:
    """Print the schema of all three source tables.

    Run this once at the start of the sprint to confirm column names.
    """
    for table in (CFG.source_facilities, CFG.source_pincode, CFG.source_nfhs5):
        print(f"\n=== {table} ===")
        spark.read.table(table).printSchema()


def sample_facility(spark: "SparkSession", n: int = 1) -> "DataFrame":
    """Return n full sample facility rows. Use to confirm field semantics."""
    return spark.read.table(CFG.source_facilities).limit(n)


# ---------------------------------------------------------------------------
# Bronze — copy source as-is into our catalog so downstream is decoupled
# ---------------------------------------------------------------------------


def load_facilities_bronze(spark: "SparkSession") -> "DataFrame":
    """Copy source facilities → bronze_facility (no transforms)."""
    df = spark.read.table(CFG.source_facilities)
    df.write.mode("overwrite").saveAsTable(CFG.fq(CFG.bronze_facility))
    return df


# ---------------------------------------------------------------------------
# Silver — clean + normalize
# ---------------------------------------------------------------------------


def build_silver_facility(spark: "SparkSession") -> "DataFrame":
    """Cleaned facility table conforming to `agent_briefs/contracts.md`.

    TODO once column names are confirmed:
      - Map source columns → silver column names
      - Normalize state + district (INITCAP, trim, collapse whitespace)
      - has_coords = (latitude IS NOT NULL AND longitude IS NOT NULL)
      - Cast year_established + capacity to INT, NULLable
    """
    bronze = spark.read.table(CFG.fq(CFG.bronze_facility))

    # Placeholder — keep raw columns until we have the real names.
    # Once `describe_sources` is run we replace this with explicit SELECT + rename.
    silver = bronze
    silver.write.mode("overwrite").saveAsTable(CFG.fq(CFG.silver_facility))
    return silver


def build_silver_pincode(spark: "SparkSession") -> "DataFrame":
    """Dedupe India Post directory to one row per pincode.

    Rule: prefer Head Office > Post Office > Branch Office.
    Tiebreaker: first row with non-null coordinates.
    """
    src = spark.read.table(CFG.source_pincode)

    # Once column names are confirmed, expected output cols per contracts.md:
    #   pincode | officename | officetype | district | statename | latitude | longitude
    # Placeholder pass-through:
    src.write.mode("overwrite").saveAsTable(CFG.fq(CFG.silver_pincode))
    return src


def build_silver_district_health(spark: "SparkSession") -> "DataFrame":
    """Clean NFHS-5.

    - Rename long column names to snake_case (already snake_case in the
      Marketplace publish per EDA — confirm).
    - For numeric indicator columns, parse strings:
        '*'       → NULL
        '(29.5)'  → 29.5, plus boolean _low_sample = TRUE
        '29.5'    → 29.5, _low_sample = FALSE
    """
    src = spark.read.table(CFG.source_nfhs5)
    # Placeholder until we confirm whether Marketplace already cleaned the suppressed values
    src.write.mode("overwrite").saveAsTable(CFG.fq(CFG.silver_district_health))
    return src


# ---------------------------------------------------------------------------
# Geographic join — facility → district polygon, with pincode fallback
# ---------------------------------------------------------------------------


def spatial_join_facility_district(spark: "SparkSession") -> "DataFrame":
    """Assign each facility a district via point-in-polygon on lat/lng.

    Strategy:
      1. Primary: ST_Contains(district_polygon, ST_Point(lng, lat))
         Polygons from geoBoundaries India ADM2 or DataMeet.
      2. Fallback (~1% of rows, per EDA): pincode lookup via silver_pincode.

    Returns DataFrame keyed by facility_id with: state_norm, district_norm,
    district_source (enum: spatial | pincode | unknown).
    """
    raise NotImplementedError("Wire geoBoundaries polygons after `describe_sources` confirms lat/lng cols")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_all_bronze(spark: "SparkSession") -> None:
    """One-shot bronze load. Idempotent."""
    load_facilities_bronze(spark)


def run_all_silver(spark: "SparkSession") -> None:
    """One-shot silver build. Run after bronze."""
    build_silver_facility(spark)
    build_silver_pincode(spark)
    build_silver_district_health(spark)
