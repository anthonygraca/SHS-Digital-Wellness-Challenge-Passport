from __future__ import annotations

from pydantic import BaseModel


class SessionOut(BaseModel):
    """What the SPA is allowed to see about the signed-in user. No PHI."""

    subject: str
    affiliation: str
    isCurrentStudent: bool
