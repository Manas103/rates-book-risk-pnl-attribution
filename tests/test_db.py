import pytest

from rates_risk import db


def test_connect_raises_cleanly_when_no_server_is_reachable():
    """PostgreSQL is not installed as a service on this build machine
    (see README); connect() must raise rather than hang or silently
    return a broken connection, so callers can skip persistence."""
    with pytest.raises(Exception):
        conn = db.connect()
        conn.close()


def test_schema_is_valid_sql_text():
    assert "CREATE TABLE IF NOT EXISTS attribution_runs" in db.SCHEMA
    assert "CREATE TABLE IF NOT EXISTS daily_attribution" in db.SCHEMA


def test_get_dsn_respects_environment_override(monkeypatch):
    monkeypatch.setenv("RATES_RISK_DSN", "dbname=custom")
    assert db.get_dsn() == "dbname=custom"
