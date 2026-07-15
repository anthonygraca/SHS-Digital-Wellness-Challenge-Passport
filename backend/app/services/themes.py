from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.theme import Theme
from app.schemas.theme import ThemeCreate, ThemeUpdate


def list_themes(db: Session) -> list[Theme]:
    rows = db.execute(select(Theme).order_by(Theme.name)).scalars().all()
    return list(rows)


def get_theme(db: Session, theme_id: str) -> Theme | None:
    return db.get(Theme, theme_id)


def create_theme(db: Session, data: ThemeCreate) -> Theme:
    theme = Theme(**data.model_dump())
    db.add(theme)
    db.commit()
    db.refresh(theme)
    return theme


def update_theme(db: Session, theme: Theme, data: ThemeUpdate) -> Theme:
    # exclude_unset (not exclude_none, as the other updaters use) so an admin can
    # explicitly clear logo_url / hero_url back to null by sending them as null.
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(theme, field, value)
    db.commit()
    db.refresh(theme)
    return theme
