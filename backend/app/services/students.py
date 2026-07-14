from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.student import Student


def get_student(db: Session, campus_id: str, sso_subject: str):
    return db.execute(
        select(Student).where(
            Student.campus_id == campus_id, Student.sso_subject == sso_subject
        )
    ).scalar_one_or_none()


def get_or_create_student(
    db: Session, campus_id: str, sso_subject: str, affiliation: str
) -> tuple[Student, bool]:
    """Load the student for (campus_id, sso_subject), or create one.

    Returns (student, created). Uniqueness is enforced by the DB constraint, so a
    returning subject never produces a duplicate. If two concurrent first-time
    logins race, the IntegrityError is caught and the winner's row is loaded.
    """
    existing = get_student(db, campus_id, sso_subject)
    if existing is not None:
        return existing, False

    student = Student(
        campus_id=campus_id, sso_subject=sso_subject, affiliation=affiliation
    )
    db.add(student)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        student = get_student(db, campus_id, sso_subject)
        assert student is not None  # the row that won the race
        return student, False
    db.refresh(student)
    return student, True
