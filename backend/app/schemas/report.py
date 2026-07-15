from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.challenge import CheckInMethod


class ReportChallengeOut(BaseModel):
    """The challenge a report covers, trimmed to what the report header shows."""

    id: int
    name: str
    semester: str
    theme_id: str

    model_config = {"from_attributes": True}


class WeekCompletionOut(BaseModel):
    """One rung of the completion funnel: how many students finished this week.

    ``week_no`` is the task's 1-based position — the week number the passport
    and the report both show. A week with nobody finished still appears, with
    ``completed_count`` of 0.
    """

    task_id: int
    week_no: int
    title: str
    required: bool
    completed_count: int


class PrizeEligibleRow(BaseModel):
    """One student who has completed every required task (FR-F5 / US-26).

    The one report that is deliberately per-student. FR-F6's "aggregate and
    privacy-aware" rule governs the FR-F1 dashboard; a drawing list cannot be
    aggregate by definition — it has to name who won a ticket. ``sso_subject``
    is the only identifier available, because Student stores no name or campus
    id on purpose (see models/student.py).

    ``required_completed``/``required_total`` are exported alongside the subject
    so a row can be audited without re-running the query: they are equal for
    every exported row, and seeing that is the point.
    """

    student_id: int
    sso_subject: str
    required_completed: int
    required_total: int
    eligible_since: datetime


class ParticipationReportOut(BaseModel):
    """Participation and the per-week completion funnel (FR-F1 / US-21).

    Counts only — no per-student rows — so the report stays aggregate and
    privacy-aware (FR-F6). The completion percentage is left to the client:
    it is a presentation choice, and the raw counts serve any renderer.
    """

    challenge: ReportChallengeOut
    total_enrollments: int
    weeks: list[WeekCompletionOut]


# The order the buckets always arrive in — automatic first, since the auto share
# is the number this report exists to show. Doubles as the seed for the
# all-three-buckets guarantee in services/reports.py.
METHOD_ORDER: tuple[CheckInMethod, ...] = ("event_qr", "staff", "manual")


class MethodCountOut(BaseModel):
    """How many check-ins one capture method accounted for.

    ``method`` reuses CheckInMethod rather than re-listing the vocabulary, so a
    fourth capture method cannot be added to the write paths without this report
    failing to validate — which is exactly the reminder we want.
    """

    method: CheckInMethod
    count: int


class AttendanceReportOut(BaseModel):
    """Auto-vs-manual attendance breakdown (FR-F2 / US-22).

    Counts only, like ParticipationReportOut: the auto *share* is a percentage,
    and percentages are the client's job (FR-F6 doctrine).

    ``total_checkins`` is shipped rather than left to be summed so the client has
    something to reconcile the buckets *against*. Summed, reconciliation would be
    vacuous, and a bucket the API failed to emit would silently redefine the
    denominator instead of showing up as a gap.

    All three methods always appear, ``staff`` included — a structural 0 today,
    since no write path mints one (passport.py writes event_qr and manual,
    checkins.py writes manual). Reporting that zero is the point: it says the
    staff-verified capture path FR-F2 anticipates is not yet wired.
    """

    challenge: ReportChallengeOut
    total_checkins: int
    methods: list[MethodCountOut]
