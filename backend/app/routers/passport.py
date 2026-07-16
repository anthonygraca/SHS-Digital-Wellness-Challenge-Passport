from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import require_current_student
from app.repositories.base import Repository, get_repo
from app.schemas.passport import (
    CheckInResult,
    PassportOut,
    ScanCheckInRequest,
    WeekOut,
)
from app.services.passport import (
    DuplicateCheckIn,
    InvalidEventToken,
    PassportView,
)

router = APIRouter()

INVALID_TOKEN_MESSAGE = "This code is no longer valid, ask the attendant"
DUPLICATE_MESSAGE = "Already completed this week"


def _event_qr_tip(title: str) -> str:
    """A stand-in personalized tip shown after check-in (FR-E1).

    Real per-task / AI-generated tips are Phase 2; this keeps the core loop honest by
    always returning a friendly, task-named message.
    """
    return (
        f"Nice work finishing {title}! Tip: try the 20-20-20 rule — every 20 minutes, "
        "look at something 20 feet away for 20 seconds to rest your eyes."
    )


def _to_passport_out(view: PassportView) -> PassportOut:
    return PassportOut(
        challengeName=view.challenge_name,
        theme=view.theme,
        totalWeeks=view.total_weeks,
        completedWeeks=view.completed_weeks,
        remainingWeeks=view.remaining_weeks,
        requiredTotal=view.required_total,
        requiredCompleted=view.required_completed,
        prizeEligible=view.prize_eligible,
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
    claims: dict = Depends(require_current_student),
    repo: Repository = Depends(get_repo),
):
    """The signed-in student's passport: week tiles with status + progress counts.

    Identity comes from the session cookie (US-1); 401 if not signed in, 403 if the
    caller is not a current student (US-2 / FR-A3). 404 if the student's campus has
    no published challenge. Serves US-5 (FR-C2, FR-C3) and the prize-eligibility
    indicator US-7 (FR-C5).
    """
    view = repo.build_passport(
        campus_id=claims["campus_id"], student_id=claims["student_id"]
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active challenge"
        )
    return _to_passport_out(view)


@router.post("/api/checkins/scan", response_model=CheckInResult)
def scan_checkin(
    payload: ScanCheckInRequest,
    claims: dict = Depends(require_current_student),
    repo: Repository = Depends(get_repo),
):
    """Record an event-QR check-in from a scanned token — the UC-3 core loop (US-8).

    The week flips to complete, the countdown updates, and a personalized tip is
    returned (FR-D1/D2, FR-E1). Gated on current-student eligibility (US-2 / FR-A3):
    a non-current student is 403 here (the "ineligible student" scenario). A tampered
    or foreign token is 400; a repeat scan of a completed week is 409.
    """
    campus_id: str = claims["campus_id"]
    student_id = claims["student_id"]
    try:
        task = repo.record_event_qr_checkin(
            campus_id=campus_id, student_id=student_id, token=payload.token
        )
    except InvalidEventToken as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_TOKEN_MESSAGE
        ) from exc
    except DuplicateCheckIn as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_MESSAGE
        ) from exc

    week_no = task.position
    title = task.title
    view = repo.build_passport(campus_id=campus_id, student_id=student_id)
    if view is None:
        # Unreachable in practice: the check-in only succeeds when an active
        # challenge exists, but keep the read path total.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active challenge"
        )
    return CheckInResult(
        passport=_to_passport_out(view),
        tip=_event_qr_tip(title),
        weekNo=week_no,
        title=title,
    )
