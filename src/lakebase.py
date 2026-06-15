"""Lakebase Postgres persistence — planner annotations + verifications.

Owner: Data Engineer.
"Persist user actions" is a hard Devpost requirement.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS verifications (
    id           BIGSERIAL PRIMARY KEY,
    facility_id  TEXT NOT NULL,
    claim_id     TEXT NOT NULL,
    planner_id   TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('verified','rejected','needs_info')),
    reason       TEXT,
    notes        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (facility_id, claim_id, planner_id)
);
CREATE INDEX IF NOT EXISTS verifications_facility_idx ON verifications (facility_id);

CREATE TABLE IF NOT EXISTS annotations (
    id           BIGSERIAL PRIMARY KEY,
    facility_id  TEXT NOT NULL,
    planner_id   TEXT NOT NULL,
    note         TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS annotations_facility_idx ON annotations (facility_id);

CREATE TABLE IF NOT EXISTS shortlists (
    id           BIGSERIAL PRIMARY KEY,
    planner_id   TEXT NOT NULL,
    name         TEXT NOT NULL,
    facility_ids TEXT[] NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (planner_id, name)
);

CREATE TABLE IF NOT EXISTS saved_searches (
    id           BIGSERIAL PRIMARY KEY,
    planner_id   TEXT NOT NULL,
    label        TEXT NOT NULL,
    query_json   JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS claim_embeddings (
    claim_id   TEXT PRIMARY KEY,
    embedding  VECTOR(1024)
);
"""


def init_schema(engine: "Engine") -> None:
    """Run once after Lakebase provisioning."""
    with engine.begin() as conn:
        from sqlalchemy import text

        for stmt in SCHEMA_SQL.split(";\n\n"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))


def record_verification(
    engine: "Engine",
    facility_id: str,
    claim_id: str,
    planner_id: str,
    status: str,
    reason: str | None = None,
    notes: str | None = None,
) -> None:
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO verifications
                  (facility_id, claim_id, planner_id, status, reason, notes)
                VALUES (:fid, :cid, :pid, :st, :rs, :nt)
                ON CONFLICT (facility_id, claim_id, planner_id)
                DO UPDATE SET status = EXCLUDED.status,
                              reason = EXCLUDED.reason,
                              notes = EXCLUDED.notes,
                              created_at = NOW()
                """
            ),
            {"fid": facility_id, "cid": claim_id, "pid": planner_id,
             "st": status, "rs": reason, "nt": notes},
        )
