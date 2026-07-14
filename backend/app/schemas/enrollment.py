from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# The friendly copy shown when a campus has no joinable challenge (US-3, scenario 3).
# Kept here so the route and any client share one source of truth.
NO_ACTIVE_CHALLENGE_CODE = "no_active_challenge"
NO_ACTIVE_CHALLENGE_MESSAGE = (
    "There's no active challenge for your campus right now. Check back soon!"
)


class ActiveChallenge(BaseModel):
    """The joinable challenge, trimmed to what the enroll UI needs."""

    id: int
    name: str

    model_config = {"from_attributes": True}


class EnrollmentStatusOut(BaseModel):
    """Drives the landing screen: is there something to join, and am I in it?"""

    active_challenge: ActiveChallenge | None
    enrolled: bool


class EnrollmentOut(BaseModel):
    """The result of joining a challenge."""

    challenge_id: int
    enrolled_at: datetime

    model_config = {"from_attributes": True}
