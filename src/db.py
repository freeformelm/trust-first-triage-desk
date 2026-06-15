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
    Uses the SDK's auth chain to get a bearer token, then calls the Lakebase
    credentials REST endpoint directly — `w.database` is not available in all
    SDK versions, so we bypass it.

    Tokens are short-lived (~1h); don't cache at engine level.
    """
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config

    cfg = Config()
    host = cfg.host.rstrip("/")
    headers = cfg.authenticate()  # returns {'Authorization': 'Bearer ...'}

    instance_name = os.environ.get("LAKEBASE_INSTANCE_NAME", "ep-solitary-shape-d8czihec")

    import requests

    resp = requests.post(
        f"{host}/api/2.0/database/instances/{instance_name}/credentials",
        headers={**headers, "Content-Type": "application/json"},
        json={"request_id": "trust-desk-app"},
        timeout=15,
    )
    if not resp.ok:
        # Fallback: try newer path used by some SDKs
        resp2 = requests.post(
            f"{host}/api/2.0/database/instances:generate-database-credential",
            headers={**headers, "Content-Type": "application/json"},
            json={"request_id": "trust-desk-app", "instance_names": [instance_name]},
            timeout=15,
        )
        if not resp2.ok:
            raise RuntimeError(
                f"Lakebase credential fetch failed. Tried both endpoints. "
                f"First: {resp.status_code} {resp.text[:200]}. "
                f"Second: {resp2.status_code} {resp2.text[:200]}"
            )
        return resp2.json().get("token") or resp2.json().get("credentials", [{}])[0].get("token")
    body = resp.json()
    return body.get("token") or body.get("credential", {}).get("token") or body["token"]


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


def triage_facilities(
    capability: str,
    state: str | None = None,
    min_trust: float = 0.0,
    limit: int = 200,
) -> pd.DataFrame:
    """One row per facility claiming the given capability, ranked by trust."""
    state_filter = "AND f.state = :state" if state else ""
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
          f.source_urls
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
    params = {"capability": capability, "min_trust": min_trust, "limit": limit}
    if state:
        params["state"] = state
    return query_delta(sql, params)


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
