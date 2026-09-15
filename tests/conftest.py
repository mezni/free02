"""Shared test fixtures: isolated Postgres/pgvector test database.

Tests run against a dedicated ``<something>_test`` database (default
``rag_test``) so the development database is never wiped by ``pytest``.
The app's engine/settings bind to it via the ``DATABASE_URL`` env var set
here before any ``src.*`` module is imported.
"""

import os

from sqlalchemy import create_engine, text

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://rag:rag@localhost:5432/rag_test",
)


def _ensure_test_database() -> str:
    """Create the test database if missing and return its URL."""
    base_url, _, dbname = TEST_DATABASE_URL.rpartition("/")
    # Safety net: refuse to test against anything that isn't clearly a test db.
    if not dbname.endswith("_test"):
        raise RuntimeError(
            f"TEST_DATABASE_URL must reference a *_test database, got {dbname!r}"
        )

    admin = create_engine(f"{base_url}/postgres", isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": dbname},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    finally:
        admin.dispose()
    return TEST_DATABASE_URL


os.environ["DATABASE_URL"] = _ensure_test_database()

import pytest

from src.db.base import Base
from src.db.session import SessionLocal, engine

_TABLES = ["chunks", "document_records", "pipeline_runs", "run_events"]


@pytest.fixture(scope="session", autouse=True)
def _schema():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(conn)
        # Keep the test schema in parity with the HNSW index from migrations.
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
                "ON chunks USING hnsw (embedding vector_cosine_ops)"
            )
        )
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