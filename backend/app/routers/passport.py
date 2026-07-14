from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_current_student
from app.db import get_db
from app.schemas.passport import CheckInRequest, PassportOut, WeekOut
from app.services.passport import PassportView, build_passport, record_manual_checkin

router = APIRouter()


def _to_passport_out(view: PassportView) -> PassportOut:
    return PassportOut(
        challengeName=view.challenge_name,
        theme=view.theme,
        totalWeeks=view.total_weeks,
        completedWeeks=view.completed_weeks,
        remainingWeeks=view.remaining_weeks,
        weeks=[
            WeekOut(
                weekNo=w.week_no,
                title=w.title,
                caption=w.caption,
                activityType=w.activity_type,
                location=w.location,
                dateStart=w.date_start,
                dateEnd=w.date_end,
                prize=w.prize,
                required=w.is_required,
                status=w.status,
            )
            for w in view.weeks
        ],
    )


@router.get("/api/passport", response_model=PassportOut)
def get_passport(
    claims: dict = Depends(require_current_student), db: Session = Depends(get_db)
):
    """The signed-in student's passport: week tiles with status + progress counts.

    Identity comes from the session cookie (US-1); 401 if not signed in, 403 if the
    caller is not a current student (US-2 / FR-A3). 404 if the student's campus has
    no published challenge. Serves US-5 (FR-C2, FR-C3).
    """
    view = build_passport(
        db, campus_id=claims["campus_id"], student_id=claims["student_id"]
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active challenge"
        )
    return _to_passport_out(view)


@router.post("/api/checkins", response_model=PassportOut)
def create_checkin(
    payload: CheckInRequest,
    claims: dict = Depends(require_current_student),
    db: Session = Depends(get_db),
):
    """Record a manual check-in for a week and return the refreshed passport.

    A demo stand-in for the QR scan (US-8) with manual unlock — any week can be
    completed directly. Idempotent, so re-tapping a completed week is harmless.
    Gated on current-student eligibility (US-2 / FR-A3), same as the read path.
    """
    record_manual_checkin(
        db,
        campus_id=claims["campus_id"],
        student_id=claims["student_id"],
        week_no=payload.weekNo,
    )
    view = build_passport(
        db, campus_id=claims["campus_id"], student_id=claims["student_id"]
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active challenge"
        )
    return _to_passport_out(view)
