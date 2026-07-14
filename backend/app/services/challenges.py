from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.challenge import Challenge, CheckIn, Enrollment, Task
from app.schemas.challenge import PassportOut, ProgressOut, TaskOut, WeekStatus


def get_active_challenge_for_campus(db: Session, campus_id: str) -> Challenge | None:
    """Get the currently active challenge for a campus (FR-B1).

    Returns the first active challenge found, or None if no active challenge exists.
    In production, there should typically be only one active challenge per campus.
    """
    stmt = (
        select(Challenge)
        .where(Challenge.campus_id == campus_id)
        .where(Challenge.status == "active")
        .order_by(Challenge.starts_on.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def get_student_enrollment(
    db: Session, student_id: int, challenge_id: int
) -> Enrollment | None:
    """Get a student's enrollment in a specific challenge (FR-C1)."""
    stmt = (
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .where(Enrollment.challenge_id == challenge_id)
    )
    return db.scalar(stmt)


def get_student_check_ins(db: Session, student_id: int, challenge_id: int) -> set[int]:
    """Get all task IDs the student has completed for a challenge.

    Returns a set of task_id values for efficient status lookups.
    """
    stmt = (
        select(CheckIn.task_id)
        .join(Task, CheckIn.task_id == Task.id)
        .where(CheckIn.student_id == student_id)
        .where(Task.challenge_id == challenge_id)
    )
    result = db.execute(stmt)
    return {task_id for (task_id,) in result}


def calculate_week_status(
    task: Task, completed_task_ids: set[int], today: date
) -> WeekStatus:
    """Calculate the status of a week/task for passport display (FR-C2).

    - complete: student has checked in
    - available: date window is active and not yet complete
    - locked: date window has not started yet
    """
    if task.id in completed_task_ids:
        return WeekStatus.COMPLETE

    # Future weeks are locked
    if today < task.date_start:
        return WeekStatus.LOCKED

    # Current or past weeks are available if not complete
    return WeekStatus.AVAILABLE


def calculate_progress(
    tasks: list[Task], completed_task_ids: set[int]
) -> ProgressOut:
    """Calculate progress summary for the passport countdown (FR-C3, FR-C5).

    Prize eligibility is derived: complete when all required tasks are checked in.
    """
    total_weeks = len(tasks)
    completed = sum(1 for task in tasks if task.id in completed_task_ids)
    remaining = total_weeks - completed

    # Prize eligibility: all required tasks must be complete (FR-C5)
    required_task_ids = {task.id for task in tasks if task.is_required}
    is_prize_eligible = required_task_ids.issubset(completed_task_ids)

    return ProgressOut(
        total_weeks=total_weeks,
        completed=completed,
        remaining=remaining,
        is_prize_eligible=is_prize_eligible,
    )


def get_student_passport(db: Session, student_id: int, campus_id: str) -> PassportOut | None:
    """Build the complete passport view for a student (UC-2).

    Returns None if:
    - No active challenge exists for the campus
    - Student is not enrolled in the active challenge

    Otherwise returns the full passport with:
    - Challenge metadata
    - All tasks with computed status (locked/available/complete)
    - Progress countdown and prize eligibility
    """
    # Find active challenge for campus
    challenge = get_active_challenge_for_campus(db, campus_id)
    if not challenge:
        return None

    # Check student enrollment
    enrollment = get_student_enrollment(db, student_id, challenge.id)
    if not enrollment:
        return None

    # Get all tasks for the challenge, ordered by week
    stmt = (
        select(Task)
        .where(Task.challenge_id == challenge.id)
        .order_by(Task.order, Task.week_no)
    )
    tasks = list(db.scalars(stmt))

    # Get student's completed tasks
    completed_task_ids = get_student_check_ins(db, student_id, challenge.id)

    # Calculate status for each task
    today = date.today()
    tasks_out = [
        TaskOut(
            id=task.id,
            challenge_id=task.challenge_id,
            week_no=task.week_no,
            title=task.title,
            caption=task.caption,
            activity_type=task.activity_type,
            location=task.location,
            date_start=task.date_start,
            date_end=task.date_end,
            is_required=task.is_required,
            order=task.order,
            status=calculate_week_status(task, completed_task_ids, today),
        )
        for task in tasks
    ]

    # Calculate progress summary
    progress = calculate_progress(tasks, completed_task_ids)

    return PassportOut(
        challenge=challenge,  # Pydantic will convert from ORM model
        tasks=tasks_out,
        progress=progress,
        enrolled_at=enrollment.enrolled_at,
    )
