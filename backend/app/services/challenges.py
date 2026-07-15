from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.challenge import AssessmentItem, Challenge, Task
from app.schemas.challenge import (
    AssessmentItemUpdate,
    ChallengeCreate,
    ChallengeUpdate,
    MCQCreate,
    ReflectionCreate,
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
        theme_id=data.theme_id,
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
# Student-facing lookups (US-3 / FR-C1)
# ---------------------------------------------------------------------------


def get_active_challenge_for_campus(db: Session, campus_id: str) -> Challenge | None:
    """The challenge a student may currently join for their campus.

    "Active" == the most recently starting *published* challenge for the campus.
    Draft challenges are not joinable, and campus isolation is enforced by the
    campus_id filter. Returns None when the campus has no published challenge.
    """
    return db.execute(
        select(Challenge)
        .where(Challenge.campus_id == campus_id, Challenge.status == "published")
        .order_by(Challenge.start_date.desc(), Challenge.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def seed_dev_challenge(db: Session, campus_id: str = "csub") -> Challenge:
    """Create (and publish) a dev challenge so the enroll flow can be exercised.

    Idempotent: if the campus already has an active (published) challenge, that
    one is returned untouched. Dev-only helper — there is no admin builder on
    this branch to create a joinable challenge manually.
    """
    existing = get_active_challenge_for_campus(db, campus_id)
    if existing is not None:
        return existing

    challenge = Challenge(
        campus_id=campus_id,
        name="Stranger Things Wellness Challenge",
        semester="Fall 2025",
        start_date=date(2025, 9, 1),
        end_date=date(2025, 12, 15),
        status="published",
    )
    db.add(challenge)
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


# ---------------------------------------------------------------------------
# Assessment item CRUD (FR-B3)
# ---------------------------------------------------------------------------


def add_assessment_item(
    db: Session, task: Task, data: MCQCreate | ReflectionCreate
) -> AssessmentItem:
    """Attach an MCQ or reflection item to a task, tagged to a learning outcome."""
    item = AssessmentItem(
        task_id=task.id,
        item_type=data.item_type,
        prompt=data.prompt,
        outcome_tag=data.outcome_tag,
        options=data.options if data.item_type == "mcq" else None,
        answer_key=data.answer_key if data.item_type == "mcq" else None,
        rubric=data.rubric if data.item_type == "reflection" else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_assessment_items(db: Session, task_id: int) -> list[AssessmentItem]:
    rows = (
        db.execute(select(AssessmentItem).where(AssessmentItem.task_id == task_id))
        .scalars()
        .all()
    )
    return list(rows)


def get_assessment_item(db: Session, task_id: int, item_id: int) -> AssessmentItem | None:
    return db.execute(
        select(AssessmentItem).where(
            AssessmentItem.id == item_id, AssessmentItem.task_id == task_id
        )
    ).scalar_one_or_none()


def update_assessment_item(
    db: Session, item: AssessmentItem, data: AssessmentItemUpdate
) -> AssessmentItem:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_assessment_item(db: Session, item: AssessmentItem) -> None:
    db.delete(item)
    db.commit()
