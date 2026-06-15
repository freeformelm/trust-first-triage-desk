"""One-shot Lakebase schema init.

Loads .env, connects to the Lakebase Postgres instance, creates the planner-state
tables defined in src/lakebase.py::SCHEMA_SQL.

Usage:  python scripts/init_lakebase.py
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

# Ensure repo root on path so `from src...` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from sqlalchemy import create_engine, text

from src.lakebase import init_schema

REQUIRED = ["LAKEBASE_HOST", "LAKEBASE_DB", "LAKEBASE_USER", "LAKEBASE_PASSWORD"]
missing = [v for v in REQUIRED if not os.environ.get(v)]
if missing:
    sys.exit(f"Missing env vars: {missing}. Populate .env first.")

# URL-encode the user (the @ in email needs encoding)
import urllib.parse

user = urllib.parse.quote(os.environ["LAKEBASE_USER"], safe="")
password = urllib.parse.quote(os.environ["LAKEBASE_PASSWORD"], safe="")
host = os.environ["LAKEBASE_HOST"]
db = os.environ["LAKEBASE_DB"]

conn_str = f"postgresql+psycopg://{user}:{password}@{host}/{db}?sslmode=require"
print(f"Connecting to {host}/{db} as {os.environ['LAKEBASE_USER']} ...")

engine = create_engine(conn_str, pool_pre_ping=True)

with engine.connect() as conn:
    version = conn.execute(text("SELECT version()")).scalar()
    print(f"Connected. Server: {version}")

print("Initializing schema ...")
init_schema(engine)
print("Done. Tables created:")

with engine.connect() as conn:
    rows = conn.execute(
        text(
            "SELECT tablename FROM pg_catalog.pg_tables "
            "WHERE schemaname='public' ORDER BY tablename"
        )
    ).fetchall()
    for r in rows:
        print(f"  - {r[0]}")
