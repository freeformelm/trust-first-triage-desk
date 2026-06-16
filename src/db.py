"""Connection helpers — Delta (via Databricks SQL connector) + Lakebase (Postgres).

Used by both notebooks (passes through SparkSession) and the Streamlit app
(uses SQL warehouse + Postgres directly).
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import pandas as pd
from databricks import sql as dbsql

from src.config import CFG


# ---------------------------------------------------------------------------
# Delta — read via Databricks SQL Warehouse
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _sql_conn():
    """Single shared connection.

    Local dev: reads DATABRICKS_TOKEN (PAT) from env.
    Deployed Databricks App: uses the SDK's default credential chain
    (auto-picks up DATABRICKS_CLIENT_ID/SECRET injected by the runtime).
    """
    server_hostname = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
    http_path = os.environ["DATABRICKS_HTTP_PATH"]

    access_token = os.environ.get("DATABRICKS_TOKEN")
    if access_token:
        return dbsql.connect(
            server_hostname=server_hostname,
            http_path=http_path,
            access_token=access_token,
        )

    # Deployed app: get token from SDK default credential chain
    from databricks.sdk.core import Config

    cfg = Config()
    return dbsql.connect(
        server_hostname=server_hostname,
        http_path=http_path,
        credentials_provider=lambda: cfg.authenticate,
    )


def query_delta(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run a parameterized SQL query against the workspace warehouse, return pandas."""
    with _sql_conn().cursor() as cur:
        cur.execute(sql, params or {})
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Lakebase Postgres — connection via psycopg / SQLAlchemy
# ---------------------------------------------------------------------------


def _fetch_lakebase_token() -> str:
    """Get a fresh OAuth token for Lakebase.

    Used when LAKEBASE_PASSWORD env var isn't set (deployed app scenario).
    Tries the SDK first (clean path); falls back to REST endpoints with
    common path variants if the SDK doesn't expose the API.
    """
    from databricks.sdk import WorkspaceClient

    instance_name = os.environ.get("LAKEBASE_INSTANCE_NAME", "ep-solitary-shape-d8czihec")
    w = WorkspaceClient()

    # 1) Preferred: SDK call (databricks-sdk >= ~0.50)
    api = getattr(w, "database", None)
    if api is not None and hasattr(api, "generate_database_credential"):
        cred = api.generate_database_credential(
            request_id="trust-desk-app",
            instance_names=[instance_name],
        )
        token = getattr(cred, "token", None)
        if token:
            return token

    # 2) Fallback: direct REST. Try several known path variants.
    from databricks.sdk.core import Config
    import requests

    cfg = Config()
    host = cfg.host.rstrip("/")
    headers = cfg.authenticate()

    candidate_calls = [
        # (path, body)
        (
            f"/api/2.0/database/instances/{instance_name}:generate-credential",
            {"request_id": "trust-desk-app"},
        ),
        (
            f"/api/2.0/database/instances/{instance_name}/generate-credential",
            {"request_id": "trust-desk-app"},
        ),
        (
            "/api/2.0/database/instances:generate-credential",
            {"request_id": "trust-desk-app", "instance_names": [instance_name]},
        ),
        (
            f"/api/2.0/database/instances/{instance_name}/credentials/generate",
            {"request_id": "trust-desk-app"},
        ),
    ]

    errors: list[str] = []
    for path, body in candidate_calls:
        try:
            resp = requests.post(
                f"{host}{path}",
                headers={**headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
        except Exception as e:
            errors.append(f"{path}: exception {e}")
            continue
        if resp.ok:
            data = resp.json()
            token = (
                data.get("token")
                or data.get("credential", {}).get("token")
                or (data.get("credentials") or [{}])[0].get("token")
            )
            if token:
                return token
            errors.append(f"{path}: 200 but no token field. body={data}")
        else:
            errors.append(f"{path}: {resp.status_code} {resp.text[:150]}")

    raise RuntimeError(
        "Lakebase credential fetch failed across all paths.\n"
        + "\n".join(errors)
    )


def lakebase_engine():
    """Fresh engine per call so OAuth tokens stay valid.

    Tokens expire in ~1h. For an in-flight planner session this is fine, but
    cache invalidation would be a bug. Re-create cheaply.
    """
    import urllib.parse
    from sqlalchemy import create_engine

    host = os.environ["LAKEBASE_HOST"]
    db = os.environ.get("LAKEBASE_DB", "databricks_postgres")
    user = os.environ["LAKEBASE_USER"]
    password = os.environ.get("LAKEBASE_PASSWORD") or _fetch_lakebase_token()
    user_q = urllib.parse.quote(user, safe="")
    password_q = urllib.parse.quote(password, safe="")
    return create_engine(
        f"postgresql+psycopg://{user_q}:{password_q}@{host}/{db}?sslmode=require",
        pool_pre_ping=True,
    )


# ---------------------------------------------------------------------------
# Domain queries used by the app
# ---------------------------------------------------------------------------


# Devpost priorities first, extended taxonomy after.
CAPABILITIES_FOR_TRIAGE = (
    "icu", "nicu", "maternity", "emergency", "oncology", "trauma",
    "surgery", "cardiology", "dialysis", "radiology", "pediatrics", "ophthalmology",
)


# ---------------------------------------------------------------------------
# Data quality audit queries (Data Quality tab)
# ---------------------------------------------------------------------------


def dq_facility_overview() -> pd.DataFrame:
    return query_delta(
        f"""
        SELECT
          COUNT(*)                                                AS total,
          COUNT_IF(has_valid_coords)                              AS valid_coords,
          COUNT_IF(NOT has_valid_coords AND latitude IS NOT NULL) AS bad_coords_dropped,
          COUNT_IF(SIZE(capabilities)  > 0)                       AS with_capability_array,
          COUNT_IF(SIZE(specialties)   > 0)                       AS with_specialties,
          COUNT_IF(SIZE(equipment)     > 0)                       AS with_equipment_array,
          COUNT_IF(SIZE(source_urls)   > 0)                       AS with_citations,
          COUNT_IF(year_established IS NOT NULL)                  AS with_year_established,
          COUNT_IF(capacity IS NOT NULL)                          AS with_capacity
        FROM {CFG.fq(CFG.silver_facility)}
        """
    )


def dq_state_source_pivot() -> pd.DataFrame:
    return query_delta(
        f"""
        SELECT state_source, COUNT(*) AS facilities
        FROM {CFG.fq(CFG.silver_facility)}
        GROUP BY state_source
        ORDER BY facilities DESC
        """
    )


def dq_status_by_capability() -> pd.DataFrame:
    return query_delta(
        f"""
        SELECT capability, status, COUNT(*) AS facilities, ROUND(AVG(trust_score), 3) AS avg_trust
        FROM {CFG.fq(CFG.gold_facility_trust)}
        GROUP BY capability, status
        ORDER BY capability, status
        """
    )


def dq_state_correction_examples(limit: int = 10) -> pd.DataFrame:
    return query_delta(
        f"""
        SELECT name, state_raw, state AS state_resolved, district, pincode
        FROM {CFG.fq(CFG.silver_facility)}
        WHERE state_source = 'pincode'
          AND state_raw IS NOT NULL
          AND state_raw <> state
        LIMIT :limit
        """,
        {"limit": limit},
    )


def triage_facilities(
    capability: str,
    state: str | None = None,
    min_trust: float = 0.0,
    limit: int = 200,
) -> pd.DataFrame:
    """One row per facility claiming the given capability, ranked by trust.

    State filter is case-insensitive prefix match against state OR city — the
    source `address_stateOrRegion` column occasionally holds a district name
    instead of a state, so accept any substring hit.
    """
    state_filter = ""
    if state:
        state_filter = (
            "AND ("
            " LOWER(f.state) LIKE LOWER(:state_q)"
            " OR LOWER(f.city)  LIKE LOWER(:state_q)"
            ")"
        )
    sql = f"""
        SELECT
          f.facility_id,
          f.name,
          f.city,
          f.state,
          f.pincode,
          f.latitude,
          f.longitude,
          t.claim_count,
          t.supporting_evidence_count,
          t.contradicting_evidence_count,
          t.trust_score,
          t.status,
          f.official_phone,
          f.official_website,
          f.source_urls,
          f.capabilities,
          f.procedures,
          f.equipment,
          f.description
        FROM {CFG.fq(CFG.gold_facility_trust)} t
        JOIN {CFG.fq(CFG.silver_facility)}    f USING (facility_id)
        WHERE t.capability = :capability
          AND t.trust_score >= :min_trust
          {state_filter}
        ORDER BY
          CASE t.status WHEN 'verified' THEN 0 WHEN 'unclear' THEN 1 ELSE 2 END,
          t.trust_score DESC
        LIMIT :limit
    """
    params: dict[str, Any] = {"capability": capability, "min_trust": min_trust, "limit": limit}
    if state:
        params["state_q"] = f"{state.strip()}%"
    return query_delta(sql, params)


def triage_counts(
    capability: str,
    state: str | None = None,
    min_trust: float = 0.0,
) -> dict[str, int]:
    """Status counts over the FULL result set (no LIMIT).

    Used by the Triage view metrics so the badges reflect reality,
    not the 200-row display cap.
    """
    state_filter = ""
    params: dict[str, Any] = {"capability": capability, "min_trust": min_trust}
    if state:
        state_filter = (
            "AND ("
            " LOWER(f.state) LIKE LOWER(:state_q)"
            " OR LOWER(f.city)  LIKE LOWER(:state_q)"
            ")"
        )
        params["state_q"] = f"{state.strip()}%"
    sql = f"""
        SELECT
          COUNT(*)                                      AS total,
          COUNT_IF(t.status = 'verified')               AS verified,
          COUNT_IF(t.status = 'unclear')                AS unclear,
          COUNT_IF(t.status = 'contradicted')           AS contradicted
        FROM {CFG.fq(CFG.gold_facility_trust)} t
        JOIN {CFG.fq(CFG.silver_facility)}    f USING (facility_id)
        WHERE t.capability = :capability
          AND t.trust_score >= :min_trust
          {state_filter}
    """
    df = query_delta(sql, params)
    if df.empty:
        return {"total": 0, "verified": 0, "unclear": 0, "contradicted": 0}
    row = df.iloc[0]
    return {
        "total": int(row["total"]),
        "verified": int(row["verified"]),
        "unclear": int(row["unclear"]),
        "contradicted": int(row["contradicted"]),
    }


def facility_detail(facility_id: str) -> pd.DataFrame:
    sql = f"""
        SELECT *
        FROM {CFG.fq(CFG.silver_facility)}
        WHERE facility_id = :fid
    """
    return query_delta(sql, {"fid": facility_id})


def facility_claims_with_evidence(facility_id: str) -> pd.DataFrame:
    sql = f"""
        SELECT
          c.claim_id,
          c.claim_type,
          c.claim_value,
          c.claim_raw,
          c.source_field,
          c.source_text_span,
          c.extraction_confidence,
          t.trust_score,
          t.status,
          t.supporting_evidence_count,
          t.contradicting_evidence_count
        FROM {CFG.fq(CFG.silver_claim)} c
        LEFT JOIN {CFG.fq(CFG.gold_facility_trust)} t
          ON t.facility_id = c.facility_id AND t.capability = c.claim_value
        WHERE c.facility_id = :fid
        ORDER BY t.trust_score DESC NULLS LAST
    """
    return query_delta(sql, {"fid": facility_id})


def facility_evidence(facility_id: str) -> pd.DataFrame:
    sql = f"""
        SELECT e.claim_id, e.snippet, e.source_field, e.polarity, e.retrieval_score
        FROM {CFG.fq(CFG.silver_evidence)} e
        JOIN {CFG.fq(CFG.silver_claim)}    c USING (claim_id)
        WHERE c.facility_id = :fid
        ORDER BY e.polarity DESC, e.retrieval_score DESC
    """
    return query_delta(sql, {"fid": facility_id})


def district_health_for(state: str, district: str | None = None) -> pd.DataFrame:
    where = "WHERE state = :state"
    params: dict[str, Any] = {"state": state}
    if district:
        where += " AND district = :district"
        params["district"] = district
    sql = f"""
        SELECT district, state,
               women_age_15_49_who_are_literate_pct,
               hh_member_covered_health_insurance_pct,
               institutional_birth_5y_pct,
               births_delivered_by_csection_5y_pct
        FROM {CFG.fq(CFG.silver_district_health)}
        {where}
        LIMIT 50
    """
    return query_delta(sql, params)


# ---------------------------------------------------------------------------
# Lakebase mutations
# ---------------------------------------------------------------------------


def record_verification(
    facility_id: str,
    claim_id: str,
    planner_id: str,
    status: str,
    reason: str | None = None,
    notes: str | None = None,
) -> None:
    from sqlalchemy import text

    with lakebase_engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO verifications (facility_id, claim_id, planner_id, status, reason, notes)
                VALUES (:fid, :cid, :pid, :st, :rs, :nt)
                ON CONFLICT (facility_id, claim_id, planner_id)
                DO UPDATE SET status = EXCLUDED.status,
                              reason = EXCLUDED.reason,
                              notes = EXCLUDED.notes,
                              created_at = NOW()
                """
            ),
            {"fid": facility_id, "cid": claim_id, "pid": planner_id, "st": status, "rs": reason, "nt": notes},
        )


def add_annotation(facility_id: str, planner_id: str, note: str) -> None:
    from sqlalchemy import text

    with lakebase_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO annotations (facility_id, planner_id, note) VALUES (:fid, :pid, :note)"
            ),
            {"fid": facility_id, "pid": planner_id, "note": note},
        )


def planner_work(planner_id: str) -> dict[str, pd.DataFrame]:
    """Return verifications + annotations dataframes for a planner."""
    import pandas as pd
    from sqlalchemy import text

    with lakebase_engine().connect() as conn:
        v = pd.read_sql(
            text("SELECT * FROM verifications WHERE planner_id = :p ORDER BY created_at DESC"),
            conn,
            params={"p": planner_id},
        )
        a = pd.read_sql(
            text("SELECT * FROM annotations WHERE planner_id = :p ORDER BY created_at DESC"),
            conn,
            params={"p": planner_id},
        )
    return {"verifications": v, "annotations": a}
