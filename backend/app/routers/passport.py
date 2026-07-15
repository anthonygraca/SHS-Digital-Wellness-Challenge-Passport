from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_current_student
from app.db import get_db
from app.schemas.engagement import ContentViewCreate
from app.schemas.passport import (
    CheckInRequest,
    CheckInResult,
    PassportOut,
    ScanCheckInRequest,
    ThemeConfigOut,
    WeekOut,
)
from app.services import engagement as engagement_svc
from app.services.passport import (
    DuplicateCheckIn,
    InvalidEventToken,
    PassportView,
    ThemeConfigView,
    build_passport,
    record_event_qr_checkin,
    record_manual_checkin,
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


def _to_theme_config_out(cfg: ThemeConfigView | None) -> ThemeConfigOut | None:
    if cfg is None:
        return None
    return ThemeConfigOut(
        id=cfg.id,
        palette=cfg.palette,
        logoUrl=cfg.logo_url,
        heroUrl=cfg.hero_url,
        appTitle=cfg.app_title,
        tagline=cfg.tagline,
        copyTone=cfg.copy_tone,
    )


def _to_passport_out(view: PassportView) -> PassportOut:
    return PassportOut(
        challengeName=view.challenge_name,
        theme=view.theme,
        themeConfig=_to_theme_config_out(view.theme_config),
        totalWeeks=view.total_weeks,
        completedWeeks=view.completed_weeks,
        remainingWeeks=view.remaining_weeks,
        requiredTotal=view.required_total,
        requiredCompleted=view.required_completed,
        prizeEligible=view.prize_eligible,
        weeks=[
            WeekOut(
                weekNo=w.week_no,
                taskId=w.task_id,
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
    no published challenge. Serves US-5 (FR-C2, FR-C3) and the prize-eligibility
    indicator US-7 (FR-C5).
    """
    view = build_passport(
        db, campus_id=claims["campus_id"], student_id=claims["student_id"]
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
    db: Session = Depends(get_db),
):
    """Record an event-QR check-in from a scanned token — the UC-3 core loop (US-8).

    The week flips to complete, the countdown updates, and a personalized tip is
    returned (FR-D1/D2, FR-E1). Gated on current-student eligibility (US-2 / FR-A3):
    a non-current student is 403 here (the "ineligible student" scenario). A tampered
    or foreign token is 400; a repeat scan of a completed week is 409.
    """
    campus_id: str = claims["campus_id"]
    student_id: int = claims["student_id"]
    try:
        task = record_event_qr_checkin(
            db, campus_id=campus_id, student_id=student_id, token=payload.token
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

    # The tip is a piece of content this route is about to deliver, so this route
    # is the only place that honestly knows it was delivered (FR-F3 / US-23). The
    # client is never asked to report it back: a POST it could drop, retry, or
    # never send would make the engagement report a measure of the client rather
    # than of the tip.
    #
    # Only the scan path. A manual check-in returns a bare passport with no tip
    # (create_checkin below), so "tip" counts tips shown, which today means scans
    # — not check-ins.
    engagement_svc.record_content_view_for_task(
        db, student_id=student_id, task=task, content_ref="tip"
    )

    view = build_passport(db, campus_id=campus_id, student_id=student_id)
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


@router.post("/api/content-views", status_code=status.HTTP_204_NO_CONTENT)
def create_content_view(
    payload: ContentViewCreate,
    claims: dict = Depends(require_current_student),
    db: Session = Depends(get_db),
):
    """Record that the student looked at a week's content (FR-F3 / US-23).

    Opening a week's detail sheet is state that only exists in the browser, so
    unlike the tip — which the scan route writes itself — this one has to be
    reported. UC-6 is what makes it worth counting: it names "opening a week"
    alongside a check-in as the moment a student meets content.

    Gated on current-student eligibility like every other student route, and
    404s on an unknown week. Both matter more here than the 204 suggests: this is
    the app's one endpoint whose whole job is to increment a number an admin will
    later read as a fact, so an ineligible caller or a made-up week number must
    not be able to move it.

    204 rather than the refreshed passport: nothing about the student's progress
    changed, and the client fires this without waiting for the answer.
    """
    view = engagement_svc.record_content_view(
        db,
        campus_id=claims["campus_id"],
        student_id=claims["student_id"],
        week_no=payload.weekNo,
        content_ref=payload.contentRef,
    )
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such week")
