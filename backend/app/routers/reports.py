from __future__ import annotations

import csv
import io
import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
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

PRIZE_CSV_COLUMNS = [
    "student_id",
    "sso_subject",
    "required_completed",
    "required_total",
    "eligible_since",
]


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


def _prize_csv_filename(challenge: Challenge) -> str:
    """A filename an admin can recognise in their downloads folder.

    The semester is admin-entered free text, so anything outside [A-Za-z0-9] is
    collapsed to a dash before it reaches a Content-Disposition header. The
    challenge id keeps two same-semester challenges from colliding.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "-", challenge.semester).strip("-")
    if not slug:
        return f"prize-eligible-{challenge.id}.csv"
    return f"prize-eligible-{slug}-{challenge.id}.csv"


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


@router.get("/prize-eligible.csv", response_class=Response)
def prize_eligible_csv(
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """The prize drawing list as CSV (FR-F5 / US-26).

    Campus-scoped to the admin's active challenge exactly like the reports above —
    the drawing is always for the challenge running right now.

    The header row is written unconditionally, so "nobody is eligible yet" is an
    empty-but-valid CSV rather than an error: it is a true answer, and the admin
    can see the file is the right shape.

    A buffered Response rather than StreamingResponse: one campus cohort is small
    enough to build in memory, and the whole body has to exist anyway to set an
    accurate download.
    """
    challenge = _active_challenge_or_404(db, claims)
    rows = report_svc.prize_eligible_students(db, challenge)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(PRIZE_CSV_COLUMNS)
    for row in rows:
        writer.writerow(
            [
                row.student_id,
                row.sso_subject,
                row.required_completed,
                row.required_total,
                row.eligible_since.isoformat(),
            ]
        )

    filename = _prize_csv_filename(challenge)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
