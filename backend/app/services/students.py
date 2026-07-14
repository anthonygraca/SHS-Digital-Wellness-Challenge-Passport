from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.student import Role, Student


def derive_role_from_affiliation(affiliation: str) -> Role:
    """Derive user role from SAML affiliation attribute (FR-A4, US-4).

    Rules:
    - "staff", "employee", "faculty" → admin
    - "student" or default → student

    The affiliation string typically contains multiple values separated by
    semicolons (e.g., "student;member" or "staff;faculty").
    """
    affiliation_lower = affiliation.lower()

    # Check for admin-granting affiliations
    admin_keywords = ["staff", "employee", "faculty", "admin"]
    if any(keyword in affiliation_lower for keyword in admin_keywords):
        return Role.ADMIN

    # Default to student
    return Role.STUDENT


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

    Role is derived from the affiliation attribute during creation (FR-A4).
    """
    existing = get_student(db, campus_id, sso_subject)
    if existing is not None:
        return existing, False

    role = derive_role_from_affiliation(affiliation)
    student = Student(
        campus_id=campus_id,
        sso_subject=sso_subject,
        affiliation=affiliation,
        role=role.value,
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
