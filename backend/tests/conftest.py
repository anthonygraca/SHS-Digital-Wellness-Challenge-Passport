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

from app.db import Base, get_db
from app.main import app
from app.models.challenge import (  # noqa: F401  (register on Base.metadata)
    AssessmentItem,
    Challenge,
    CheckIn,
    Task,
)
from app.models.student import Student  # noqa: F401  (register on Base.metadata)
from app.models.theme import Theme  # noqa: F401  (register on Base.metadata)


def pytest_bdd_apply_tag(tag, function):
    """Turn a Gherkin tag into a selectable pytest marker.

    pytest-bdd's default is `getattr(pytest.mark, tag)`, which yields marker names
    like "FR-D6" and "source:UC-11". Those are not Python identifiers, so `-m` —
    which parses its argument as a Python expression — reads "FR-D6" as subtraction
    and chokes on the colon outright. Normalizing to "FR_D6" / "source_UC_11" keeps
    the .feature files verbatim against docs/features.md while making `-m FR_D6` work.
    """
    name = tag.replace("-", "_").replace(":", "_").replace(".", "_")
    getattr(pytest.mark, name)(function)
    return True  # handled — skip pytest-bdd's default tagging


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
    def _override_get_db():
        db = db_sessionmaker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    # Plain TestClient (no context manager) so app startup/init_db does not run;
    # the fixture owns table creation on the in-memory StaticPool engine.
    yield TestClient(app)
    app.dependency_overrides.clear()
