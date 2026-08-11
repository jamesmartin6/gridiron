"""Test setup: points the app at a throwaway `..._test` database (same
server as DATABASE_URL, different name) so tests never touch dev data, then
creates/drops the schema around the whole session and truncates between
tests.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

_base_url = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://gridiron:gridiron@localhost:5432/gridiron"
)
_root, _, _dbname = _base_url.rpartition("/")
TEST_DB_NAME = f"{_dbname}_test"
os.environ["DATABASE_URL"] = f"{_root}/{TEST_DB_NAME}"


def _ensure_test_database() -> None:
    from sqlalchemy import create_engine, text

    admin_engine = create_engine(f"{_root}/postgres", isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()


_ensure_test_database()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def db_session():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
