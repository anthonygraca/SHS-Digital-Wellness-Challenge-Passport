"""Aggregate reporting over a challenge (UC-10 / FR-F1).

Read-only and cohort-wide, which is what separates this from passport.py: that
module derives one student's progress, this one counts across all of them. Both
answer "is this week complete?" the same way — a CheckIn row for the week's Task
— so the funnel and a student's own passport can never disagree.

Nothing is cached or stored: every request re-derives the counts, so a check-in
recorded a second ago is in the next refresh (US-21, scenario 2).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.challenge import Challenge, CheckIn, Enrollment, Task
from app.schemas.report import (
    ParticipationReportOut,
    ReportChallengeOut,
    WeekCompletionOut,
)


def participation_report(db: Session, challenge: Challenge) -> ParticipationReportOut:
    """Total enrollments plus the per-week completion funnel for one challenge.

    The caller resolves the challenge campus-scoped; filtering both queries by
    its id is what keeps another campus's rows out of the counts.
    """
    total_enrollments = (
        db.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.challenge_id == challenge.id)
        )
        or 0
    )

    # LEFT OUTER JOIN, not an inner one: a week nobody has finished yet must
    # still appear in the funnel as a zero, otherwise the drop-off the report
    # exists to show would be invisible.
    #
    # count(distinct student_id) rather than count(*): uq_checkin_student_task
    # already makes those equal, but the funnel counts *students*, and saying so
    # keeps the query honest if that constraint ever loosens.
    rows = db.execute(
        select(
            Task.id,
            Task.position,
            Task.title,
            Task.required,
            func.count(func.distinct(CheckIn.student_id)).label("completed_count"),
        )
        .outerjoin(CheckIn, CheckIn.task_id == Task.id)
        .where(Task.challenge_id == challenge.id)
        .group_by(Task.id, Task.position, Task.title, Task.required)
        .order_by(Task.position)
    ).all()

    return ParticipationReportOut(
        challenge=ReportChallengeOut.model_validate(challenge),
        total_enrollments=total_enrollments,
        weeks=[
            WeekCompletionOut(
                task_id=task_id,
                week_no=position,
                title=title,
                required=required,
                completed_count=completed_count,
            )
            for task_id, position, title, required, completed_count in rows
        ],
    )
