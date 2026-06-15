"""Central config for the Trust-First Triage Desk.

All catalog / schema / endpoint names live here. Override via env vars.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    workspace_url: str = os.getenv(
        "DATABRICKS_HOST", "https://dbc-faa88b0d-a49b.cloud.databricks.com"
    )
    profile: str = os.getenv("DATABRICKS_PROFILE", "databricks_hackathon")

    # Source Marketplace tables (read-only)
    source_catalog: str = "databricks_virtue_foundation_dataset_dais_2026"
    source_schema: str = "virtue_foundation_dataset"
    source_facilities: str = "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities"
    source_pincode: str = "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.india_post_pincode_directory"
    source_nfhs5: str = "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.nfhs_5_district_health_indicators"

    # Our writable Unity Catalog
    catalog: str = os.getenv("UC_CATALOG", "hackathon")
    schema: str = os.getenv("UC_SCHEMA", "trust_desk")

    # Our tables
    bronze_facility: str = "bronze_facility"
    silver_facility: str = "silver_facility"
    silver_claim: str = "silver_claim"
    silver_evidence: str = "silver_evidence"
    silver_pincode: str = "silver_pincode"
    silver_district_health: str = "silver_district_health"
    gold_facility_trust: str = "gold_facility_trust"
    claim_extraction_cache: str = "claim_extraction_cache"

    # LLM endpoint — Databricks Foundation Model APIs (Free Edition)
    llm_endpoint: str = os.getenv("LLM_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
    embedding_endpoint: str = os.getenv(
        "EMBEDDING_ENDPOINT", "databricks-gte-large-en"
    )

    # Lakebase
    lakebase_host: str = os.getenv("LAKEBASE_HOST", "")
    lakebase_db: str = os.getenv("LAKEBASE_DB", "databricks_postgres")
    lakebase_user: str = os.getenv("LAKEBASE_USER", "")

    # Claim taxonomy (Devpost called these out explicitly)
    capability_taxonomy: tuple[str, ...] = (
        "icu",
        "maternity",
        "emergency",
        "oncology",
        "trauma",
        "nicu",
        "surgery",
        "cardiology",
        "dialysis",
        "radiology",
        "pediatrics",
        "ophthalmology",
    )

    def fq(self, table: str) -> str:
        """Fully qualified table name: catalog.schema.table"""
        return f"{self.catalog}.{self.schema}.{table}"


CFG = Config()
