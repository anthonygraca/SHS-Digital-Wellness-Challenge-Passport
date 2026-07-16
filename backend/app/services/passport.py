from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.challenge import Challenge, CheckIn, Task
from app.models.theme import Theme
from app.services.challenges import get_active_challenge_for_campus
from app.services.qr import verify_event_token

WeekStatus = Literal["locked", "available", "complete"]


@dataclass
class WeekView:
    week_no: int
    title: str
    caption: str
    activity_type: str
    location: str
    date_start: date | None
    date_end: date | None
    prize: str
    is_required: bool
    status: WeekStatus


@dataclass
class ThemeConfigView:
    """The challenge's theme resolved to everything the app needs to skin itself.

    Sending the resolved config (not just the id) is what makes a re-skin pure
    configuration — the student app never ships per-theme code (FR-B4 / NFR-6).
    """

    id: str
    palette: dict[str, str]
    logo_url: str | None
    hero_url: str | None
    app_title: str
    tagline: str
    copy_tone: str


@dataclass
class PassportView:
    challenge_name: str
    theme: str
    theme_config: ThemeConfigView | None
    total_weeks: int
    completed_weeks: int
    remaining_weeks: int
    required_total: int
    required_completed: int
    prize_eligible: bool
    weeks: list[WeekView]


def _resolve_theme(db: Session, theme_id: str) -> ThemeConfigView | None:
    """Load the challenge's theme row, or None for the default/unknown theme.

    Resolved on every request, so an admin's edit shows up on the student's next
    fetch with no cache to invalidate (US-13 scenario 3). An empty or dangling
    ``theme_id`` degrades to the app's default skin rather than erroring.
    """
    if not theme_id:
        return None
    theme = db.get(Theme, theme_id)
    if theme is None:
        return None
    return ThemeConfigView(
        id=theme.id,
        palette=dict(theme.palette or {}),
        logo_url=theme.logo_url,
        hero_url=theme.hero_url,
        app_title=theme.app_title,
        tagline=theme.tagline,
        copy_tone=theme.copy_tone,
    )


def build_passport(
    db: Session, *, campus_id: str, student_id: int
) -> PassportView | None:
    """Assemble a student's passport view for their campus's published challenge.

    Status is *derived*, never stored (architecture-plan.md:141,149): a week is
    ``complete`` when the student has a check-in for it; otherwise the earliest
    not-yet-complete week is ``available`` and every later week is ``locked``
    (sequential unlock, matching the prototype). Returns ``None`` when no published
    challenge exists for the campus.

    A task's ``position`` (its 1-based order in the admin builder) is what the
    passport surfaces as the week number.
    """
    challenge = get_active_challenge_for_campus(db, campus_id)
    if challenge is None:
        return None
    return build_passport_for(db, challenge=challenge, student_id=student_id)


def build_passport_for(
    db: Session, *, challenge: Challenge, student_id: int
) -> PassportView:
    """:func:`build_passport` for an already-resolved challenge — see the repo protocol.

    On SQL both lookups are cheap session queries; this exists to keep the seam
    uniform with the Dynamo path, where the saved round trip is real.
    """
    tasks = list(
        db.execute(
            select(Task).where(Task.challenge_id == challenge.id).order_by(Task.position)
        ).scalars()
    )

    completed_ids: set[int] = set()
    if tasks:
        completed_ids = set(
            db.execute(
                select(CheckIn.task_id).where(
                    CheckIn.student_id == student_id,
                    CheckIn.task_id.in_([t.id for t in tasks]),
                )
            ).scalars()
        )

    return assemble_passport(
        challenge_name=challenge.name,
        theme=challenge.theme_id,
        tasks=tasks,
        completed_ids=completed_ids,
        theme_config=_resolve_theme(db, challenge.theme_id),
    )


def assemble_passport(
    *,
    challenge_name: str,
    theme: str,
    tasks: list,
    completed_ids: set,
    theme_config: ThemeConfigView | None = None,
) -> PassportView:
    """Pure derivation of the passport view from a challenge's tasks + completions.

    Backend-agnostic: ``tasks`` is any ordered sequence of objects exposing the
    task attributes (ORM rows on the SQL path, ``TaskDTO`` on the Dynamo path), and
    ``completed_ids`` is the set of the student's completed task ids (already scoped
    to these tasks). Both persistence backends call this so the sequential-unlock and
    prize-eligibility rules live in exactly one place.

    ``theme_config`` is resolved by the caller (SQL: :func:`_resolve_theme`; Dynamo:
    a Themes point-read) and threaded through unchanged, so this stays free of any
    persistence dependency while still carrying the resolved skin (FR-B4 / US-13).
    """
    weeks: list[WeekView] = []
    available_assigned = False
    for task in tasks:
        status: WeekStatus
        if task.id in completed_ids:
            status = "complete"
        elif not available_assigned:
            status = "available"
            available_assigned = True
        else:
            status = "locked"
        weeks.append(
            WeekView(
                week_no=task.position,
                title=task.title,
                caption=task.caption,
                activity_type=task.activity_type,
                location=task.location,
                date_start=task.date_window_start,
                date_end=task.date_window_end,
                prize=task.prize,
                is_required=task.required,
                status=status,
            )
        )

    completed = len(completed_ids)
    total = len(tasks)

    # Prize eligibility (US-7 / FR-C5) is a *derived* query, never a stored flag:
    # a student is eligible once every required task is complete. Optional tasks
    # (``required`` False) are ignored. Guard on there being at least one required
    # task so an all-optional challenge never reads as "eligible" for free.
    required_total = sum(1 for t in tasks if t.required)
    required_completed = sum(1 for t in tasks if t.required and t.id in completed_ids)
    prize_eligible = required_total > 0 and required_completed == required_total

    return PassportView(
        challenge_name=challenge_name,
        theme=theme,
        theme_config=theme_config,
        total_weeks=total,
        completed_weeks=completed,
        remaining_weeks=total - completed,
        required_total=required_total,
        required_completed=required_completed,
        prize_eligible=prize_eligible,
        weeks=weeks,
    )


class InvalidEventToken(Exception):
    """The scanned QR is missing/tampered or points at no live event for this campus."""


class DuplicateCheckIn(Exception):
    """The student already has a check-in for this task/week."""


def record_event_qr_checkin(
    db: Session, *, campus_id: str, student_id: int, token: str
) -> Task:
    """Record an ``event_qr`` check-in from a scanned event QR (UC-3 core loop, US-8).

    Validates that ``token`` is a well-signed event token whose task belongs to the
    campus's active published challenge, then records exactly one check-in. Raises
    ``InvalidEventToken`` for a bad/foreign token and ``DuplicateCheckIn`` when the
    student already completed that task (race-safe via the unique constraint). Returns
    the completed ``Task`` so the caller can surface the week number, title, and tip.

    Deliberately applies no date-window or expiry gate yet (deferred with US-9), and
    no enrollment gate — eligibility is the current-student check on the route.
    """
    task_id = verify_event_token(token)
    if task_id is None:
        raise InvalidEventToken

    challenge = get_active_challenge_for_campus(db, campus_id)
    if challenge is None:
        raise InvalidEventToken

    task = db.get(Task, task_id)
    if task is None or task.challenge_id != challenge.id:
        raise InvalidEventToken

    existing = db.execute(
        select(CheckIn).where(
            CheckIn.student_id == student_id, CheckIn.task_id == task.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicateCheckIn

    db.add(CheckIn(student_id=student_id, task_id=task.id, method="event_qr"))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateCheckIn from exc
    return task
