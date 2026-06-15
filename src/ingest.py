"""Bronze + Silver ingest for FDR facility data + supplementals.

Owner: Data Engineer.
Run as a Databricks notebook or job. Single-node Spark is fine — 10k rows.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.config import CFG

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession


def load_fdr_to_bronze(spark: "SparkSession", marketplace_table: str) -> "DataFrame":
    """Load Virtue Foundation FDR (Marketplace) → bronze_facility.

    Assumes the marketplace listing has been installed and exposes a table at
    `marketplace_table`. Filter to India only.
    """
    df = spark.read.table(marketplace_table)
    # Adjust filter once we see the actual country column name
    df_india = df.filter("upper(country) = 'INDIA'")
    df_india.write.mode("overwrite").saveAsTable(CFG.fq(CFG.bronze_facility))
    return df_india


def bronze_to_silver_facility(spark: "SparkSession") -> "DataFrame":
    """Normalize column names, district/state, validate lat/lng."""
    bronze = spark.read.table(CFG.fq(CFG.bronze_facility))
    # TODO: snake_case rename, district normalization, lat/lng range check
    # Placeholder: persist as-is
    bronze.write.mode("overwrite").saveAsTable(CFG.fq(CFG.silver_facility))
    return bronze


def load_pincode_directory(spark: "SparkSession", csv_path: str) -> "DataFrame":
    """India Post PIN Code Directory → silver_pincode.

    NOTE: grain = post office. Dedupe to one row per pincode before any join.
    """
    df = (
        spark.read.option("header", True)
        .option("inferSchema", True)
        .csv(csv_path)
    )
    # Dedupe: prefer Head Office > Post Office > Branch Office; pick first with non-NA coords
    # TODO implement priority dedupe
    df.write.mode("overwrite").saveAsTable(CFG.fq(CFG.silver_pincode))
    return df


def load_nfhs5(spark: "SparkSession", csv_path: str) -> "DataFrame":
    """NFHS-5 district indicators → silver_district_health.

    - Rename long column names to snake_case
    - Convert `*` (suppressed) → NULL
    - Convert `(29.5)` (low-sample estimate) → 29.5 with a paired `_low_sample` boolean flag
    """
    df = (
        spark.read.option("header", True)
        .option("inferSchema", False)  # parse strings, clean ourselves
        .csv(csv_path)
    )
    # TODO: rename + cleaning pass
    df.write.mode("overwrite").saveAsTable(CFG.fq(CFG.silver_district_health))
    return df


def spatial_join_facility_district(spark: "SparkSession") -> "DataFrame":
    """Assign each facility a district by point-in-polygon on lat/lng.

    Polygons: geoBoundaries India ADM2 or DataMeet India Maps.
    Fallback: pincode → district via silver_pincode lookup.
    """
    # TODO implement with Databricks geospatial functions or geopandas
    raise NotImplementedError
