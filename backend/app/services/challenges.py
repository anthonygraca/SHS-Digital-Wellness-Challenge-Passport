from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.challenge import Challenge, Task
from app.schemas.challenge import (
    ChallengeCreate,
    ChallengeUpdate,
    TaskCreate,
    TaskReorder,
    TaskUpdate,
)

# ---------------------------------------------------------------------------
# Challenge CRUD
# ---------------------------------------------------------------------------


def create_challenge(db: Session, campus_id: str, data: ChallengeCreate) -> Challenge:
    challenge = Challenge(
        campus_id=campus_id,
        name=data.name,
        semester=data.semester,
        start_date=data.start_date,
        end_date=data.end_date,
        status="draft",
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def list_challenges(db: Session, campus_id: str) -> list[Challenge]:
    rows = (
        db.execute(
            select(Challenge)
            .where(Challenge.campus_id == campus_id)
            .order_by(Challenge.created_at.desc())
        )
        .scalars()
        .all()
    )
    return list(rows)


def get_challenge(db: Session, campus_id: str, challenge_id: int) -> Challenge | None:
    return db.execute(
        select(Challenge).where(
            Challenge.id == challenge_id, Challenge.campus_id == campus_id
        )
    ).scalar_one_or_none()


def update_challenge(
    db: Session, challenge: Challenge, data: ChallengeUpdate
) -> Challenge:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(challenge, field, value)
    db.commit()
    db.refresh(challenge)
    return challenge


def publish_challenge(db: Session, challenge: Challenge) -> Challenge:
    challenge.status = "published"
    db.commit()
    db.refresh(challenge)
    return challenge


# ---------------------------------------------------------------------------
# Task CRUD
# ---------------------------------------------------------------------------


def _next_position(db: Session, challenge_id: int) -> int:
    """Return the next available 1-based position for a new task."""
    rows = (
        db.execute(select(Task).where(Task.challenge_id == challenge_id)).scalars().all()
    )
    return len(rows) + 1


def add_task(db: Session, challenge: Challenge, data: TaskCreate) -> Task:
    position = _next_position(db, challenge.id)
    task = Task(
        challenge_id=challenge.id,
        position=position,
        title=data.title,
        caption=data.caption,
        activity_type=data.activity_type,
        location=data.location,
        date_window_start=data.date_window_start,
        date_window_end=data.date_window_end,
        prize=data.prize,
        required=data.required,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, challenge_id: int, task_id: int) -> Task | None:
    return db.execute(
        select(Task).where(Task.id == task_id, Task.challenge_id == challenge_id)
    ).scalar_one_or_none()


def update_task(db: Session, task: Task, data: TaskUpdate) -> Task:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: Task) -> None:
    challenge_id = task.challenge_id
    position = task.position
    db.delete(task)
    db.flush()
    # Close the gap: decrement positions above the deleted one.
    remaining = (
        db.execute(
            select(Task)
            .where(Task.challenge_id == challenge_id, Task.position > position)
            .order_by(Task.position)
        )
        .scalars()
        .all()
    )
    for t in remaining:
        t.position -= 1
    db.commit()


def reorder_tasks(db: Session, challenge: Challenge, data: TaskReorder) -> list[Task]:
    """Assign new positions from the ordered task_ids list.

    Validates that the supplied IDs are exactly the tasks belonging to the
    challenge — no more, no fewer.
    """
    existing = (
        db.execute(select(Task).where(Task.challenge_id == challenge.id)).scalars().all()
    )
    existing_ids = {t.id for t in existing}
    incoming_ids = set(data.task_ids)

    if existing_ids != incoming_ids:
        raise ValueError(
            "task_ids must contain exactly the IDs of all tasks in this challenge"
        )

    task_map = {t.id: t for t in existing}
    for new_position, task_id in enumerate(data.task_ids, start=1):
        task_map[task_id].position = new_position

    db.commit()
    # Return in new order.
    updated = (
        db.execute(
            select(Task).where(Task.challenge_id == challenge.id).order_by(Task.position)
        )
        .scalars()
        .all()
    )
    return list(updated)
