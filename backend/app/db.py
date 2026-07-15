from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(_settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables, then seed demo data. Imports models so they register on Base."""
    from app.models import (
        challenge,  # noqa: F401
        student,  # noqa: F401
        theme,  # noqa: F401
    )

    Base.metadata.create_all(bind=engine)

    from app.services.seed import seed_demo_challenge, seed_themes

    with SessionLocal() as db:
        seed_themes(db)
        seed_demo_challenge(db)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
