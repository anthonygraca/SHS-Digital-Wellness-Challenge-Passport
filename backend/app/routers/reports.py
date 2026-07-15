from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_admin
from app.db import get_db
from app.schemas.enrollment import (
    NO_ACTIVE_CHALLENGE_CODE,
    NO_ACTIVE_CHALLENGE_MESSAGE,
)
from app.schemas.report import ParticipationReportOut
from app.services import challenges as challenge_svc
from app.services import reports as report_svc

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/participation", response_model=ParticipationReportOut)
def participation_report(
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Participation and the per-week completion funnel (FR-F1 / US-21).

    Scoped to the admin's own active challenge rather than an id in the path:
    the report always describes "the challenge running right now" for the
    admin's campus, so the SPA needs one request rather than a lookup then a
    fetch. Resolving it here also means campus isolation is enforced before any
    counting happens.
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

    return report_svc.participation_report(db, challenge)
