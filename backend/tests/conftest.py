from __future__ import annotations

import os

# Point the app engine at an in-memory DB before anything imports settings, so tests
# never touch a real file. The client uses its own StaticPool engine (below) anyway.
os.environ.setdefault("WP_DATABASE_URL", "sqlite://")
os.environ.setdefault("WP_AUTH_PROVIDER", "mock")
os.environ.setdefault("WP_JWT_SECRET", "test-secret-at-least-32-bytes-long-000")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app
from app.models.challenge import (  # noqa: F401  (register on Base.metadata)
    AssessmentItem,
    Challenge,
    CheckIn,
    Task,
)
from app.models.student import Student  # noqa: F401  (register on Base.metadata)
from app.repositories.base import get_repo
from app.repositories.sqlalchemy_repo import SqlAlchemyRepository


@pytest.fixture
def db_sessionmaker():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def client(db_sessionmaker):
    def _override_get_repo():
        db = db_sessionmaker()
        try:
            yield SqlAlchemyRepository(db)
        finally:
            db.close()

    app.dependency_overrides[get_repo] = _override_get_repo
    # Plain TestClient (no context manager) so app startup/init_db does not run;
    # the fixture owns table creation on the in-memory StaticPool engine.
    yield TestClient(app)
    app.dependency_overrides.clear()
