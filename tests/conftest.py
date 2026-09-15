"""Shared test fixtures: Postgres/pgvector schema and isolated-empty tables per test."""

import pytest
from sqlalchemy import text

from src.db.base import Base
from src.db.session import SessionLocal, engine

_TABLES = ["chunks", "document_records", "pipeline_runs", "run_events"]


@pytest.fixture(scope="session", autouse=True)
def _schema():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(conn)
    yield


@pytest.fixture(autouse=True)
def _clean_tables(_schema):
    with engine.begin() as conn:
        for table in _TABLES:
            conn.execute(text(f"DELETE FROM {table}"))
    yield


@pytest.fixture
def db_session():
    """Function-scoped SQLAlchemy session (callers commit their own writes)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()