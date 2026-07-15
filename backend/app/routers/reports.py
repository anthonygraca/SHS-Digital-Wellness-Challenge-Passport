from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.deps import require_admin
from app.db import get_db
from app.models.challenge import Challenge
from app.schemas.enrollment import (
    NO_ACTIVE_CHALLENGE_CODE,
    NO_ACTIVE_CHALLENGE_MESSAGE,
)
from app.schemas.report import (
    AttendanceReportOut,
    EngagementReportOut,
    ParticipationReportOut,
)
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


def _report_challenge_or_404(
    db: Session, claims: dict, challenge_id: int | None
) -> Challenge:
    """Resolve the challenge every report in this router describes.

    Omit ``challenge_id`` and this answers for the campus's active challenge —
    "the challenge running right now", which is what an admin opening the
    dashboard means. Pass one and it answers for that challenge instead, which is
    what US-23's "both can be viewed per challenge" asks for and what makes a past
    semester reportable at all.

    Either way the campus comes from the caller's own claims and never from the
    request, so campus isolation is enforced here, before any counting happens.
    An id belonging to another campus is a **404, not a 403** — the convention
    services/challenges.py already follows, so a report cannot be used to probe
    which challenge ids exist elsewhere.

    Published-only in both branches. The active resolver only ever returns a
    published challenge, and an explicit id is held to the same rule rather than
    quietly becoming the one way to report on a draft: "draft" means still being
    authored, and its counts would describe a challenge no student could join.

    Still shared by every route in this file, and now more load-bearing than
    before: it is why one selector moves all four answers at once, so two cards on
    one dashboard can never disagree about which challenge they describe.
    """
    if challenge_id is None:
        challenge = challenge_svc.get_active_challenge_for_campus(db, claims["campus_id"])
    else:
        challenge = challenge_svc.get_challenge(db, claims["campus_id"], challenge_id)
        if challenge is not None and challenge.status != "published":
            challenge = None

    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": NO_ACTIVE_CHALLENGE_CODE,
                "message": NO_ACTIVE_CHALLENGE_MESSAGE,
            },
        )
    return challenge


def _utc_iso(ts: datetime) -> str:
    """One timestamp shape in the file, whatever the database gave back.

    Check-ins are always written in UTC, but SQLite doesn't keep the offset that
    DateTime(timezone=True) carries, so the same row reads back naive on sqlite
    and UTC-aware on postgres — and would otherwise export two different strings.
    Re-attach the offset the writer guaranteed and print one of them. Seconds
    resolution: this column says which day someone qualified, not which
    microsecond, and the file's own order already carries the tie-break.
    """
    aware = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
    return (
        aware.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


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
    challenge_id: int | None = Query(None),
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Participation and the per-week completion funnel (FR-F1 / US-21)."""
    return report_svc.participation_report(
        db, _report_challenge_or_404(db, claims, challenge_id)
    )


@router.get("/attendance", response_model=AttendanceReportOut)
def attendance_report(
    challenge_id: int | None = Query(None),
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Auto-vs-manual attendance breakdown (FR-F2 / US-22).

    Its own route rather than a block on /participation: the two count different
    things — students who finished a week vs. check-ins captured — and one grain
    per response keeps each readable as one FR. Both resolve the challenge the
    same way, so they always answer for the same one and 404 together.
    """
    return report_svc.attendance_report(
        db, _report_challenge_or_404(db, claims, challenge_id)
    )


@router.get("/engagement", response_model=EngagementReportOut)
def engagement_report(
    challenge_id: int | None = Query(None),
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Content views and guide usage (FR-F3 / US-23).

    Its own route for the reason /attendance is: a third grain — content looked
    at, rather than weeks finished or check-ins captured — and one grain per
    response keeps each response readable as one FR.

    ``challenge_id`` is what US-23's "both can be viewed per challenge" asks for.
    It lands on every route in this file rather than just this one so the cards
    on one dashboard always describe the same challenge.
    """
    return report_svc.engagement_report(
        db, _report_challenge_or_404(db, claims, challenge_id)
    )


@router.get("/prize-eligible.csv", response_class=Response)
def prize_eligible_csv(
    challenge_id: int | None = Query(None),
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """The prize drawing list as CSV (FR-F5 / US-26).

    Campus-scoped exactly like the reports above, and takes the same
    ``challenge_id``. That it follows the dashboard's selector is not a nicety:
    the export is a *record* an admin acts on, and a drawing run against last
    semester's list because the file quietly ignored the selector would be a real
    error with real prizes attached.

    The header row is written unconditionally, so "nobody is eligible yet" is an
    empty-but-valid CSV rather than an error: it is a true answer, and the admin
    can see the file is the right shape.

    A buffered Response rather than StreamingResponse: one campus cohort is small
    enough to build in memory, and the whole body has to exist anyway to set an
    accurate download.
    """
    challenge = _report_challenge_or_404(db, claims, challenge_id)
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
                _utc_iso(row.eligible_since),
            ]
        )

    filename = _prize_csv_filename(challenge)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
