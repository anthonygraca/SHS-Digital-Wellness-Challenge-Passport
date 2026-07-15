from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# A theme id doubles as the frontend's data-theme attribute value, so it must be
# a plain slug — no spaces, no quotes, nothing that could break a CSS selector.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ThemeCreate(BaseModel):
    """Payload for adding a re-skin preset (FR-B4)."""

    id: str = Field(..., max_length=64)
    name: str
    palette: dict[str, str] = Field(default_factory=dict)
    logo_url: str | None = None
    hero_url: str | None = None
    app_title: str = "Wellness Passport"
    tagline: str = ""
    copy_tone: str = ""

    @field_validator("id")
    @classmethod
    def id_is_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "id must be a lowercase slug (letters, digits and hyphens only)"
            )
        return v


class ThemeUpdate(BaseModel):
    """Partial update — all fields optional; ``id`` is immutable.

    ``palette`` replaces the stored map wholesale rather than merging, so a
    caller removing a token sends the map without it.
    """

    name: str | None = None
    palette: dict[str, str] | None = None
    logo_url: str | None = None
    hero_url: str | None = None
    app_title: str | None = None
    tagline: str | None = None
    copy_tone: str | None = None


class ThemeOut(BaseModel):
    id: str
    name: str
    palette: dict[str, str]
    logo_url: str | None
    hero_url: str | None
    app_title: str
    tagline: str
    copy_tone: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
