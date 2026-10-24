"""Optional PostgreSQL persistence for the daily attribution run. Real
schema, exercised against psycopg2's own connection-error path when no
server is reachable (PostgreSQL is not installed as a service on this
build machine; see README). Every number in this repository's README is
computed in-process without requiring a live database, the same posture
`futures-strategy-backtester/futbt/db.py` takes for its own optional
PostgreSQL layer.
"""
from __future__ import annotations

import os

SCHEMA = """
CREATE TABLE IF NOT EXISTS attribution_runs (
    run_id SERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    num_sessions INTEGER NOT NULL,
    pct_unexplained DOUBLE PRECISION NOT NULL,
    summary JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_attribution (
    run_id INTEGER NOT NULL REFERENCES attribution_runs(run_id),
    session INTEGER NOT NULL,
    actual_pnl DOUBLE PRECISION NOT NULL,
    curve DOUBLE PRECISION NOT NULL,
    carry DOUBLE PRECISION NOT NULL,
    spread DOUBLE PRECISION NOT NULL,
    residual DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (run_id, session)
);
"""


def get_dsn() -> str:
    return os.environ.get("RATES_RISK_DSN", "dbname=rates_risk user=postgres host=localhost port=5432")


def connect():
    """Raises psycopg2.OperationalError (or ImportError if psycopg2 is not
    installed) when no server is reachable; callers are expected to catch
    that and skip persistence, never to require a live database for the
    attribution numbers themselves."""
    import psycopg2

    return psycopg2.connect(get_dsn())


def init_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()


def save_run(conn, num_sessions: int, pct_unexplained: float, summary: dict, rows: list) -> int:
    import json

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO attribution_runs (num_sessions, pct_unexplained, summary) VALUES (%s, %s, %s) RETURNING run_id",
            (num_sessions, pct_unexplained, json.dumps(summary)),
        )
        run_id = cur.fetchone()[0]
        cur.executemany(
            """INSERT INTO daily_attribution (run_id, session, actual_pnl, curve, carry, spread, residual)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [(run_id, r["session"], r["actual_pnl"], r["curve"], r["carry"], r["spread"], r["residual"]) for r in rows],
        )
    conn.commit()
    return run_id
