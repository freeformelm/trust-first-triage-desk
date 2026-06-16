"""Bronze + Silver ingest for FDR facility data + supplementals.

Owner: Data Engineer.
Source schema confirmed 2026-06-15 — see `agent_briefs/contracts.md`.

Source (read-only, from Databricks Marketplace listing
`19326b3d-db63-4627-abc0-cf4e8131a305`):
  - databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities  (10,088 rows, 51 cols)
  - ...india_post_pincode_directory  (165,627 rows, 11 cols)
  - ...nfhs_5_district_health_indicators  (706 rows, 109 cols, snake_case already)

Target (writable):
  - hackathon.trust_desk.*  (override via UC_CATALOG / UC_SCHEMA env vars)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.config import CFG

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession


# ---------------------------------------------------------------------------
# Discovery helpers — keep for reproducibility
# ---------------------------------------------------------------------------


def describe_sources(spark: "SparkSession") -> None:
    for table in (CFG.source_facilities, CFG.source_pincode, CFG.source_nfhs5):
        print(f"\n=== {table} ===")
        spark.read.table(table).printSchema()


def sample_facility(spark: "SparkSession", n: int = 1) -> "DataFrame":
    return spark.read.table(CFG.source_facilities).limit(n)


# ---------------------------------------------------------------------------
# India bounding box (filters out bad geocoding — confirmed bad row in sample)
# ---------------------------------------------------------------------------

INDIA_LAT_MIN, INDIA_LAT_MAX = 6.0, 37.0
INDIA_LNG_MIN, INDIA_LNG_MAX = 68.0, 98.0


# ---------------------------------------------------------------------------
# Bronze — copy source as-is
# ---------------------------------------------------------------------------


def load_facilities_bronze(spark: "SparkSession") -> "DataFrame":
    df = spark.read.table(CFG.source_facilities)
    df.write.mode("overwrite").saveAsTable(CFG.fq(CFG.bronze_facility))
    return df


# ---------------------------------------------------------------------------
# Silver — clean + normalize + parse JSON arrays
# ---------------------------------------------------------------------------


def build_silver_facility(spark: "SparkSession") -> "DataFrame":
    """Clean facility table conforming to `agent_briefs/contracts.md`.

    Transforms:
      - Rename source → silver columns (snake_case)
      - Parse JSON-array string fields
      - Cast numeric strings
      - Normalize state + city (INITCAP, trim, collapse whitespace)
      - Validate lat/lng against India bounding box → `has_valid_coords`
      - Surface trust-signal columns from FDR
      - **Resolve state + district via pincode lookup** when raw `address_stateOrRegion`
        actually contains a district name (real source-data quality issue confirmed in EDA).
        Keeps `state_raw` + `district_raw` for audit; adds `state`, `district`, `state_source`.

    Requires `silver_pincode` to exist first (see `run_all_silver` orchestration).
    """
    df = spark.read.table(CFG.fq(CFG.bronze_facility))
    df.createOrReplaceTempView("_bronze_facility")

    # Build interim view with raw fields
    spark.sql(
        f"""
        CREATE OR REPLACE TEMP VIEW _facility_interim AS
        SELECT
          unique_id                                                      AS facility_id,
          TRIM(name)                                                     AS name,
          LOWER(NULLIF(TRIM(organization_type), ''))                     AS organization_type,
          LOWER(NULLIF(TRIM(facilityTypeId), ''))                        AS facility_type,
          LOWER(NULLIF(TRIM(operatorTypeId), ''))                        AS operator_type,
          description,
          ARRAY_DISTINCT(FROM_JSON(specialties, 'array<string>'))        AS specialties,
          ARRAY_DISTINCT(FROM_JSON(procedure,   'array<string>'))        AS procedures,
          ARRAY_DISTINCT(FROM_JSON(equipment,   'array<string>'))        AS equipment,
          ARRAY_DISTINCT(FROM_JSON(capability,  'array<string>'))        AS capabilities,
          ARRAY_DISTINCT(FROM_JSON(source_urls, 'array<string>'))        AS source_urls,
          TRY_CAST(capacity        AS INT)                               AS capacity,
          TRY_CAST(yearEstablished AS INT)                               AS year_established,
          TRY_CAST(numberDoctors   AS INT)                               AS number_doctors,
          INITCAP(TRIM(REGEXP_REPLACE(address_stateOrRegion, '\\\\s+', ' '))) AS state_raw,
          INITCAP(TRIM(REGEXP_REPLACE(address_city, '\\\\s+', ' ')))          AS city,
          NULLIF(TRIM(address_zipOrPostcode), '')                        AS pincode,
          address_line1, address_line2, address_line3,
          address_country, address_countryCode AS address_country_code,
          latitude,
          longitude,
          (latitude  BETWEEN {INDIA_LAT_MIN} AND {INDIA_LAT_MAX}
           AND longitude BETWEEN {INDIA_LNG_MIN} AND {INDIA_LNG_MAX})    AS has_valid_coords,
          recency_of_page_update,
          TRY_CAST(distinct_social_media_presence_count AS INT)          AS social_media_presence_count,
          (LOWER(affiliated_staff_presence) = 'true')                    AS has_affiliated_staff,
          (LOWER(custom_logo_presence) = 'true')                         AS has_custom_logo,
          TRY_CAST(number_of_facts_about_the_organization AS INT)        AS facts_count,
          officialPhone                                                  AS official_phone,
          email,
          officialWebsite                                                AS official_website,
          source_content_id,
          cluster_id
        FROM _bronze_facility
        """
    )

    # Pincode lookup table (already deduped, one row per pincode)
    pincode_tbl = CFG.fq(CFG.silver_pincode)

    # Known Indian states + UTs (canonical) — used as backup validator
    indian_states_sql = ", ".join(
        f"'{s}'" for s in (
            "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
            "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
            "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
            "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha",
            "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
            "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
            "Andaman And Nicobar Islands", "Chandigarh",
            "Dadra And Nagar Haveli And Daman And Diu", "Delhi",
            "Jammu And Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
        )
    )

    silver = spark.sql(
        f"""
        WITH joined AS (
          SELECT
            f.*,
            p.statename AS pincode_state,
            p.district  AS pincode_district
          FROM _facility_interim f
          LEFT JOIN {pincode_tbl} p
            ON f.pincode = p.pincode
        )
        SELECT
          facility_id, name, organization_type, facility_type, operator_type, description,
          specialties, procedures, equipment, capabilities, source_urls,
          capacity, year_established, number_doctors,

          -- Raw values preserved for audit
          state_raw,
          pincode_district AS district_raw,

          -- Resolved canonical state: pincode > state_raw (if in known list) > NULL
          COALESCE(
            pincode_state,
            CASE WHEN state_raw IN ({indian_states_sql}) THEN state_raw ELSE NULL END
          ) AS state,
          pincode_district AS district,
          CASE
            WHEN pincode_state IS NOT NULL THEN 'pincode'
            WHEN state_raw IN ({indian_states_sql}) THEN 'source'
            ELSE 'unresolved'
          END AS state_source,

          city,
          pincode,
          address_line1, address_line2, address_line3,
          address_country, address_country_code,
          latitude, longitude, has_valid_coords,
          recency_of_page_update,
          social_media_presence_count,
          has_affiliated_staff, has_custom_logo, facts_count,
          official_phone, email, official_website,
          source_content_id, cluster_id
        FROM joined
        """
    )

    silver.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        CFG.fq(CFG.silver_facility)
    )
    return silver


def build_silver_pincode(spark: "SparkSession") -> "DataFrame":
    """Dedupe India Post directory to one row per pincode.

    Source: `pincode` is LONG, `latitude`/`longitude` are STRING. Parse to numeric.

    Rule: prefer Head Office > Post Office > Branch Office; tiebreaker = first row with non-null coords.
    """
    df = spark.read.table(CFG.source_pincode)
    df.createOrReplaceTempView("_src_pincode")

    deduped = spark.sql(
        """
        WITH ranked AS (
          SELECT
            CAST(pincode AS STRING)                  AS pincode,
            officename,
            officetype,
            INITCAP(TRIM(district))                  AS district,
            INITCAP(TRIM(statename))                 AS statename,
            TRY_CAST(NULLIF(latitude,  'NA') AS DOUBLE) AS latitude,
            TRY_CAST(NULLIF(longitude, 'NA') AS DOUBLE) AS longitude,
            ROW_NUMBER() OVER (
              PARTITION BY pincode
              ORDER BY
                CASE upper(officetype)
                  WHEN 'HO' THEN 1
                  WHEN 'PO' THEN 2
                  WHEN 'BO' THEN 3
                  ELSE 4
                END,
                CASE WHEN latitude  IS NOT NULL AND latitude  <> 'NA' THEN 0 ELSE 1 END,
                officename
            ) AS rn
          FROM _src_pincode
        )
        SELECT pincode, officename, officetype, district, statename, latitude, longitude
        FROM ranked
        WHERE rn = 1
        """
    )
    deduped.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        CFG.fq(CFG.silver_pincode)
    )
    return deduped


def build_silver_district_health(spark: "SparkSession") -> "DataFrame":
    """NFHS-5 — already snake_case in source. Normalize district + state cols.

    Some indicator cols are typed string (suppressed `*` / parenthesized estimates).
    For demo simplicity, keep them as-is in silver. Downstream callers should
    `TRY_CAST(value AS DOUBLE)` and treat parse failures as low-sample / NULL.
    """
    df = spark.read.table(CFG.source_nfhs5)
    df.createOrReplaceTempView("_src_nfhs5")

    silver = spark.sql(
        """
        SELECT
          INITCAP(TRIM(REGEXP_REPLACE(district_name, '\\\\s+', ' '))) AS district,
          INITCAP(TRIM(REGEXP_REPLACE(state_ut,      '\\\\s+', ' '))) AS state,
          *
        FROM _src_nfhs5
        """
    )
    silver.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        CFG.fq(CFG.silver_district_health)
    )
    return silver


# ---------------------------------------------------------------------------
# Geographic join — fallback only (we already have facility lat/lng in 98.83%)
# ---------------------------------------------------------------------------


def attach_district_via_pincode(spark: "SparkSession") -> "DataFrame":
    """Cheap fallback: facility pincode → silver_pincode.district.

    For rows without valid coords. Spatial join via geoBoundaries is the
    higher-quality path — wire in Phase 2 only if time permits.
    """
    return spark.sql(
        f"""
        SELECT f.facility_id,
               COALESCE(f.state, p.statename)  AS state_resolved,
               p.district                       AS district_resolved,
               'pincode'                        AS district_source
        FROM   {CFG.fq(CFG.silver_facility)} f
        LEFT   JOIN {CFG.fq(CFG.silver_pincode)} p
               ON f.pincode = p.pincode
        """
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_all_bronze(spark: "SparkSession") -> None:
    load_facilities_bronze(spark)


def run_all_silver(spark: "SparkSession") -> None:
    # Pincode FIRST — silver_facility joins against it for state resolution
    build_silver_pincode(spark)
    build_silver_district_health(spark)
    build_silver_facility(spark)
