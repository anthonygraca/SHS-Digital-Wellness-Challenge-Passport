from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.challenge import Challenge, CheckIn, Task


@dataclass
class WeekView:
    week_no: int
    title: str
    caption: str
    activity_type: str
    location: str
    date_start: date
    date_end: date
    prize: str
    is_required: bool
    status: str  # "locked" | "available" | "complete"


@dataclass
class PassportView:
    challenge_name: str
    theme: str
    total_weeks: int
    completed_weeks: int
    remaining_weeks: int
    weeks: list[WeekView]


def get_active_challenge(db: Session, campus_id: str) -> Challenge | None:
    """The active challenge for a campus (newest first if more than one)."""
    return (
        db.execute(
            select(Challenge)
            .where(Challenge.campus_id == campus_id, Challenge.status == "active")
            .order_by(Challenge.starts_on.desc())
        )
        .scalars()
        .first()
    )


def build_passport(
    db: Session, *, campus_id: str, student_id: int
) -> PassportView | None:
    """Assemble a student's passport view for their campus's active challenge.

    Status is *derived*, never stored (architecture-plan.md:141,149): a week is
    ``complete`` when the student has a check-in for it; otherwise the earliest
    not-yet-complete week is ``available`` and every later week is ``locked``
    (sequential unlock, matching the prototype). Returns ``None`` when no active
    challenge exists for the campus.
    """
    challenge = get_active_challenge(db, campus_id)
    if challenge is None:
        return None

    tasks = list(
        db.execute(
            select(Task).where(Task.challenge_id == challenge.id).order_by(Task.week_no)
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

    weeks: list[WeekView] = []
    available_assigned = False
    for task in tasks:
        if task.id in completed_ids:
            status = "complete"
        elif not available_assigned:
            status = "available"
            available_assigned = True
        else:
            status = "locked"
        weeks.append(
            WeekView(
                week_no=task.week_no,
                title=task.title,
                caption=task.caption,
                activity_type=task.activity_type,
                location=task.location,
                date_start=task.date_start,
                date_end=task.date_end,
                prize=task.prize,
                is_required=task.is_required,
                status=status,
            )
        )

    completed = len(completed_ids)
    total = len(tasks)
    return PassportView(
        challenge_name=challenge.name,
        theme=challenge.theme_id,
        total_weeks=total,
        completed_weeks=completed,
        remaining_weeks=total - completed,
        weeks=weeks,
    )


def record_manual_checkin(
    db: Session, *, campus_id: str, student_id: int, week_no: int
) -> bool:
    """Record a manual completion for a week — a demo stand-in for the QR scan (US-8).

    "Manual unlock": deliberately applies no sequential/date gate, so any week can be
    completed directly. Idempotent — returns False if the task is missing or the student
    already has a check-in for it, True when a new one is recorded.
    """
    challenge = get_active_challenge(db, campus_id)
    if challenge is None:
        return False

    task = db.execute(
        select(Task).where(Task.challenge_id == challenge.id, Task.week_no == week_no)
    ).scalar_one_or_none()
    if task is None:
        return False

    existing = db.execute(
        select(CheckIn).where(
            CheckIn.student_id == student_id, CheckIn.task_id == task.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False

    db.add(CheckIn(student_id=student_id, task_id=task.id, method="manual"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True
