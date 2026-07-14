from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.deps import current_claims
from app.db import get_db
from app.schemas.challenge import PassportOut
from app.services.challenges import get_student_passport

router = APIRouter(prefix="/api", tags=["challenges"])


@router.get("/passport", response_model=PassportOut)
def get_passport(request: Request, db: Session = Depends(get_db)):
    """Get the authenticated student's passport view (UC-2, US-5).

    Returns the active challenge with all weeks/tasks showing:
    - Status: locked (future), available (current/past not done), complete (done)
    - Progress countdown: "X of Y complete, Z remaining"
    - Prize eligibility indicator

    Returns 401 if not authenticated.
    Returns 404 if no active challenge or student not enrolled.
    """
    claims = current_claims(request)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in"
        )

    student_id = claims.get("student_id")
    campus_id = claims.get("campus_id")

    if not student_id or not campus_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session: missing student_id or campus_id",
        )

    passport = get_student_passport(db, student_id=student_id, campus_id=campus_id)

    if passport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active challenge found or you are not enrolled",
        )

    return passport
