from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import require_current_student
from app.repositories.base import Repository, get_repo
from app.schemas.enrollment import (
    NO_ACTIVE_CHALLENGE_CODE,
    NO_ACTIVE_CHALLENGE_MESSAGE,
    ActiveChallenge,
    EnrollmentOut,
    EnrollmentStatusOut,
)

router = APIRouter()


@router.get("/enrollment", response_model=EnrollmentStatusOut)
def enrollment_status(
    claims: dict = Depends(require_current_student),
    repo: Repository = Depends(get_repo),
):
    """Tell the SPA whether there's a joinable challenge and if the student is in it.

    Drives the landing screen's three US-3 branches: no active challenge, already
    enrolled (go straight to the passport), or not-yet-enrolled (show Join).
    """
    challenge = repo.get_active_challenge(claims["campus_id"])
    if challenge is None:
        return EnrollmentStatusOut(active_challenge=None, enrolled=False)

    enrolled = repo.get_enrollment(claims["student_id"], challenge.id) is not None
    return EnrollmentStatusOut(
        active_challenge=ActiveChallenge.model_validate(challenge), enrolled=enrolled
    )


@router.post("/enrollment", response_model=EnrollmentOut)
def enroll(
    claims: dict = Depends(require_current_student),
    repo: Repository = Depends(get_repo),
):
    """Enroll the signed-in current student in the active challenge (FR-C1 / US-3).

    The ``require_current_student`` gate (US-2) blocks non-students with a 403
    before this runs. Enrollment is idempotent — joining twice returns the
    existing record rather than creating a duplicate. If the campus has no
    published challenge, responds 404 with a friendly ``no_active_challenge``
    payload the SPA can branch on.
    """
    challenge = repo.get_active_challenge(claims["campus_id"])
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": NO_ACTIVE_CHALLENGE_CODE,
                "message": NO_ACTIVE_CHALLENGE_MESSAGE,
            },
        )

    return repo.enroll(claims["student_id"], challenge.id)
