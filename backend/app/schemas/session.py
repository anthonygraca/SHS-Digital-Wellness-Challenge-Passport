from __future__ import annotations

from pydantic import BaseModel


class SessionOut(BaseModel):
    """What the SPA is allowed to see about the signed-in user. No PHI (FR-A2, FR-A4)."""

    subject: str
    affiliation: str
    isCurrentStudent: bool
    role: str
    student_id: int  # Database ID for check-ins and enrollments
