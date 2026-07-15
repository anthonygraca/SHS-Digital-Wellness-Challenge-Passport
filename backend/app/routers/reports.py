from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_admin
from app.db import get_db
from app.models.challenge import Challenge
from app.schemas.enrollment import (
    NO_ACTIVE_CHALLENGE_CODE,
    NO_ACTIVE_CHALLENGE_MESSAGE,
)
from app.schemas.report import AttendanceReportOut, ParticipationReportOut
from app.services import challenges as challenge_svc
from app.services import reports as report_svc

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _active_challenge_or_404(db: Session, claims: dict) -> Challenge:
    """Resolve the challenge every report in this router describes.

    Scoped to the admin's own active challenge rather than an id in the path: a
    report always describes "the challenge running right now" for the admin's
    campus, so the SPA needs one request rather than a lookup then a fetch.
    Resolving it here also means campus isolation is enforced before any counting
    happens. Shared by every route so two cards on one dashboard can never
    disagree about which challenge they are describing.
    """
    challenge = challenge_svc.get_active_challenge_for_campus(db, claims["campus_id"])
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": NO_ACTIVE_CHALLENGE_CODE,
                "message": NO_ACTIVE_CHALLENGE_MESSAGE,
            },
        )
    return challenge


@router.get("/participation", response_model=ParticipationReportOut)
def participation_report(
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Participation and the per-week completion funnel (FR-F1 / US-21)."""
    return report_svc.participation_report(db, _active_challenge_or_404(db, claims))


@router.get("/attendance", response_model=AttendanceReportOut)
def attendance_report(
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Auto-vs-manual attendance breakdown (FR-F2 / US-22).

    Its own route rather than a block on /participation: the two count different
    things — students who finished a week vs. check-ins captured — and one grain
    per response keeps each readable as one FR. Both resolve the challenge the
    same way, so they always answer for the same one and 404 together.
    """
    return report_svc.attendance_report(db, _active_challenge_or_404(db, claims))
