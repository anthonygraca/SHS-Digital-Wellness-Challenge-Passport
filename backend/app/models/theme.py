from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Theme(Base):
    """A named re-skin preset (FR-B4 / US-13).

    Global rather than campus-scoped: themes are shared presets an admin picks
    per challenge via ``Challenge.theme_id``. Every attribute is mutable so a
    semester re-skin — palette, logo, hero art, copy tone — is a configuration
    change, never a code change (NFR-6).

    ``id`` is a slug that doubles as the frontend's ``data-theme`` attribute
    value, so a theme still skins the app from the static token blocks in
    tokens.css even if its row is missing.
    """

    __tablename__ = "themes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Map of CSS custom-property suffix -> value, e.g. {"primary": "#ff4438"}.
    # Stored without the --wp- prefix; the frontend adds it when applying.
    palette: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Absolute or app-relative URLs. There is no asset store on this branch, so
    # admins supply URLs rather than uploading files.
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    hero_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Copy tone (US-13 scenario 3): the words the student app renders.
    app_title: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Wellness Passport"
    )
    tagline: Mapped[str] = mapped_column(Text, nullable=False, default="")
    copy_tone: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
