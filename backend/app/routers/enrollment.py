from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.deps import require_current_student

router = APIRouter()


@router.post("/enrollment")
def enroll(claims: dict = Depends(require_current_student)):
    """Enroll the signed-in student in the active challenge.

    US-2 only builds the current-student eligibility gate: the
    ``require_current_student`` dependency blocks non-students with a 403 before
    this body runs. Creating the actual enrollment record is US-3 (FR-C1).
    """
    # TODO(US-3): look up the active challenge and create an Enrollment row.
    return {"eligible": True}
