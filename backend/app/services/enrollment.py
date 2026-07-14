from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.challenge import Enrollment


def get_enrollment(
    db: Session, student_id: int, challenge_id: int
) -> Enrollment | None:
    return db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.challenge_id == challenge_id,
        )
    ).scalar_one_or_none()


def get_or_create_enrollment(
    db: Session, student_id: int, challenge_id: int
) -> tuple[Enrollment, bool]:
    """Enroll the student in the challenge, or return their existing enrollment.

    Returns (enrollment, created). The (student_id, challenge_id) unique
    constraint makes this idempotent — a second call never creates a duplicate,
    satisfying US-3 "Student cannot enroll twice". If two concurrent first-time
    enrollments race, the IntegrityError is caught and the winner's row loaded.
    """
    existing = get_enrollment(db, student_id, challenge_id)
    if existing is not None:
        return existing, False

    enrollment = Enrollment(student_id=student_id, challenge_id=challenge_id)
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        enrollment = get_enrollment(db, student_id, challenge_id)
        assert enrollment is not None  # the row that won the race
        return enrollment, False
    db.refresh(enrollment)
    return enrollment, True
