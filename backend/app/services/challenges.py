from __future__ import annotations

import copy
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.challenge import AssessmentItem, Challenge, Task
from app.schemas.challenge import (
    AssessmentItemUpdate,
    ChallengeCreate,
    ChallengeDuplicate,
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
# Duplication (FR-B6 / US-14)
# ---------------------------------------------------------------------------

_COPY_SUFFIX_RE = re.compile(r"\s*\(Copy(?: \d+)?\)$")

# Bounded so a campus that has somehow accumulated a hundred copies fails loudly
# instead of looping; the router turns the ValueError into a 409.
_MAX_COPY_ATTEMPTS = 100


def _unique_copy_name(db: Session, campus_id: str, name: str, semester: str) -> str:
    """First free "<base> (Copy)" / "<base> (Copy N)" for this campus + semester.

    An existing copy suffix is stripped from the base first, so duplicating a
    copy yields "X (Copy 2)" rather than "X (Copy) (Copy)".
    """
    base = _COPY_SUFFIX_RE.sub("", name)
    for n in range(1, _MAX_COPY_ATTEMPTS + 1):
        candidate = f"{base} (Copy)" if n == 1 else f"{base} (Copy {n})"
        taken = db.execute(
            select(Challenge.id).where(
                Challenge.campus_id == campus_id,
                Challenge.name == candidate,
                Challenge.semester == semester,
            )
        ).first()
        if taken is None:
            return candidate
    raise ValueError("Could not derive a unique name for the copy")


def duplicate_challenge(
    db: Session, campus_id: str, original: Challenge, data: ChallengeDuplicate
) -> Challenge:
    """Deep-copy a challenge into a new editable draft (FR-B6 / US-14).

    Copies the tasks (in position order) and their assessment items, plus the
    theme_id. Deliberately not copied: id, status (a copy is always a draft),
    timestamps, enrollments, and check-ins — those belong to the original's run.

    Dates come over verbatim. There is no academic calendar to shift a semester
    against, and the copy is a draft that students cannot see until it is
    published, so the admin edits them before they mean anything.
    """
    semester = data.semester if data.semester is not None else original.semester
    name = (
        data.name
        if data.name is not None
        else _unique_copy_name(db, campus_id, original.name, semester)
    )

    dup = Challenge(
        campus_id=campus_id,
        name=name,
        semester=semester,
        start_date=original.start_date,
        end_date=original.end_date,
        theme_id=original.theme_id,
        status="draft",
    )

    # The relationship is order_by=Task.position, so copying position verbatim
    # preserves the gapless 1..N invariant. Task QR tokens need no handling:
    # TaskOut.qr_token is derived from the task id, so copies mint their own.
    for task in original.tasks:
        new_task = Task(
            position=task.position,
            title=task.title,
            caption=task.caption,
            activity_type=task.activity_type,
            location=task.location,
            date_window_start=task.date_window_start,
            date_window_end=task.date_window_end,
            prize=task.prize,
            required=task.required,
        )
        for item in task.assessment_items:
            new_task.assessment_items.append(
                AssessmentItem(
                    item_type=item.item_type,
                    prompt=item.prompt,
                    outcome_tag=item.outcome_tag,
                    # options is a plain JSON column, not a MutableList: assigning
                    # it across would alias one list onto both rows until the
                    # commit below re-serializes them apart. Defensive, not load-
                    # bearing — nothing in this function mutates the list in place,
                    # so no test can distinguish it. It keeps the in-memory graph
                    # honest for anything that reads `dup` before the commit.
                    options=copy.deepcopy(item.options),
                    answer_key=item.answer_key,
                    rubric=item.rubric,
                )
            )
        dup.tasks.append(new_task)

    db.add(dup)
    try:
        db.commit()
    except IntegrityError as exc:
        # Backstops uq_challenge_campus_name_sem: an explicit colliding name, or
        # a racing duplicate that took the probed name between SELECT and INSERT.
        db.rollback()
        raise ValueError(
            "A challenge with that name already exists for that semester"
        ) from exc
    db.refresh(dup)
    return dup


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
