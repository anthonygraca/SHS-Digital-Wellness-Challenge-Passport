"""Manual completion override + audit (FR-D6 / US-27).

Separate from ``challenges.py``, which owns *authoring* (FR-B1/B2/B3) over
Challenge/Task/AssessmentItem. This module owns *completion + audit* over
CheckIn/CheckInAudit/Student — a different concern with a different model set,
following the same one-service-per-concern split as passport.py and enrollment.py.

The load-bearing invariant: every mutator writes its CheckIn change and its
CheckInAudit row under a single commit, so a completion can never change without
leaving a trace.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.challenge import CheckIn, CheckInAudit, Task
from app.models.student import Student


def checkin_snapshot(checkin: CheckIn, student: Student) -> dict:
    """A self-contained JSON snapshot of a check-in.

    Carries student_subject (not just the id) so the row still means something
    after the student or task it referenced is gone. ``ts`` is isoformat'd
    because SQLAlchemy's JSON column cannot serialize a datetime.

    Public because the DynamoDB repository builds the same snapshots for the same
    ledger: reading attributes only, it works on the ORM rows here and on the DTOs
    there, which keeps an audit row identical whichever backend wrote it.
    """
    return {
        "checkin_id": checkin.id,
        "student_id": checkin.student_id,
        "student_subject": student.sso_subject,
        "task_id": checkin.task_id,
        "ts": checkin.ts.isoformat() if checkin.ts else None,
        "method": checkin.method,
        "verified_by": checkin.verified_by,
    }


def _audit(
    db: Session,
    *,
    campus_id: str,
    action: str,
    student_id: int,
    task_id: int,
    checkin_id: int | None,
    actor_subject: str,
    reason: str,
    prior: dict | None,
    new: dict | None,
) -> CheckInAudit:
    """Stage an audit row. The caller owns the commit."""
    audit = CheckInAudit(
        campus_id=campus_id,
        action=action,
        student_id=student_id,
        task_id=task_id,
        checkin_id=checkin_id,
        actor_subject=actor_subject,
        reason=reason,
        prior_state=prior,
        new_state=new,
    )
    db.add(audit)
    return audit


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def get_checkin(db: Session, task_id: int, checkin_id: int) -> CheckIn | None:
    return db.execute(
        select(CheckIn).where(CheckIn.id == checkin_id, CheckIn.task_id == task_id)
    ).scalar_one_or_none()


def get_checkin_for_student(db: Session, student_id: int, task_id: int) -> CheckIn | None:
    return db.execute(
        select(CheckIn).where(
            CheckIn.student_id == student_id, CheckIn.task_id == task_id
        )
    ).scalar_one_or_none()


def list_task_checkins(db: Session, task_id: int) -> list[tuple[CheckIn, Student]]:
    """Every check-in for a task, paired with its student for subject display."""
    rows = db.execute(
        select(CheckIn, Student)
        .join(Student, Student.id == CheckIn.student_id)
        .where(CheckIn.task_id == task_id)
        .order_by(CheckIn.ts.desc())
    ).all()
    return [(checkin, student) for checkin, student in rows]


def count_task_checkins(db: Session, task_id: int) -> int:
    """How many students have checked in for a task (FR-D4 / US-28)."""
    return db.execute(
        select(func.count()).select_from(CheckIn).where(CheckIn.task_id == task_id)
    ).scalar_one()


def list_recent_task_checkins(db: Session, task_id: int, limit: int) -> list[CheckIn]:
    """The newest ``limit`` check-ins for a task, newest first.

    No Student join, unlike :func:`list_task_checkins`: the caller is the projected
    live dashboard, which identifies students by check-in number only.
    """
    return list(
        db.execute(
            select(CheckIn)
            .where(CheckIn.task_id == task_id)
            .order_by(CheckIn.ts.desc(), CheckIn.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def list_task_audits(
    db: Session, task_id: int, student_id: int | None = None
) -> list[CheckInAudit]:
    """The audit ledger for a task, newest first."""
    stmt = select(CheckInAudit).where(CheckInAudit.task_id == task_id)
    if student_id is not None:
        stmt = stmt.where(CheckInAudit.student_id == student_id)
    stmt = stmt.order_by(CheckInAudit.ts.desc(), CheckInAudit.id.desc())
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Mutators — each writes the change + its audit row under one commit
# ---------------------------------------------------------------------------


def create_manual_checkin(
    db: Session,
    *,
    campus_id: str,
    task: Task,
    student: Student,
    actor_subject: str,
    reason: str,
    ts: datetime | None = None,
) -> CheckIn:
    """Record an admin-marked completion (FR-D6).

    ``verified_by`` is set to the acting admin. Since the student-facing manual
    check-in was removed (#98, QR-only) — a student now completes a task only by
    scanning, which writes ``method="event_qr"`` — ``method="manual"`` is written
    only by an admin override, and every one leaves an audit row beside it.

    Raises ValueError if the student already has a check-in for this task; the
    router maps that to 409. Overriding an existing one is correct_checkin.
    """
    checkin = CheckIn(
        student_id=student.id,
        task_id=task.id,
        method="manual",
        verified_by=actor_subject,
    )
    if ts is not None:
        checkin.ts = ts
    db.add(checkin)
    try:
        # Flush (not commit) to surface the uq_checkin_student_task collision and
        # to assign checkin.id before it is snapshotted into new_state.
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Student already has a check-in for this task") from exc

    _audit(
        db,
        campus_id=campus_id,
        action="create",
        student_id=student.id,
        task_id=task.id,
        checkin_id=checkin.id,
        actor_subject=actor_subject,
        reason=reason,
        prior=None,
        new=checkin_snapshot(checkin, student),
    )
    db.commit()
    db.refresh(checkin)
    return checkin


def correct_checkin(
    db: Session,
    *,
    campus_id: str,
    checkin: CheckIn,
    student: Student,
    actor_subject: str,
    reason: str,
    method: str | None = None,
    ts: datetime | None = None,
) -> CheckIn:
    """Correct an existing check-in, preserving the prior state for audit."""
    prior = checkin_snapshot(checkin, student)

    if method is not None:
        checkin.method = method
    if ts is not None:
        checkin.ts = ts
    checkin.verified_by = actor_subject
    db.flush()

    _audit(
        db,
        campus_id=campus_id,
        action="update",
        student_id=checkin.student_id,
        task_id=checkin.task_id,
        checkin_id=checkin.id,
        actor_subject=actor_subject,
        reason=reason,
        prior=prior,
        new=checkin_snapshot(checkin, student),
    )
    db.commit()
    db.refresh(checkin)
    return checkin


def remove_checkin(
    db: Session,
    *,
    campus_id: str,
    checkin: CheckIn,
    student: Student,
    actor_subject: str,
    reason: str,
) -> None:
    """Hard-delete a check-in. The prior_state snapshot is what survives it."""
    # Snapshot BEFORE the delete — afterwards the attributes are expired.
    prior = checkin_snapshot(checkin, student)
    student_id, task_id, checkin_id = checkin.student_id, checkin.task_id, checkin.id

    db.delete(checkin)
    _audit(
        db,
        campus_id=campus_id,
        action="delete",
        student_id=student_id,
        task_id=task_id,
        checkin_id=checkin_id,
        actor_subject=actor_subject,
        reason=reason,
        prior=prior,
        new=None,
    )
    db.commit()
