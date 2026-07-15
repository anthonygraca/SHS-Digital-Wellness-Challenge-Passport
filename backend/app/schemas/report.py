from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.challenge import CheckInMethod
from app.schemas.engagement import ContentRef


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


# The order the content buckets always arrive in. Week detail first: it is the
# view a student chooses to make, where a tip is one they are handed. Doubles as
# the seed for the all-refs-always guarantee in services/reports.py.
CONTENT_REF_ORDER: tuple[ContentRef, ...] = ("week_detail", "tip")


class ContentRefCountOut(BaseModel):
    """How many views one piece of content accounted for.

    ``content_ref`` reuses ContentRef rather than re-listing the vocabulary, for
    the reason MethodCountOut reuses CheckInMethod: a third kind of content
    cannot be added to the write paths without this report failing to validate.
    """

    content_ref: ContentRef
    count: int


class EngagementReportOut(BaseModel):
    """Content views and guide usage (FR-F3 / US-23).

    Counts only, like the reports above — how the views divide as a percentage is
    the client's job (FR-F6 doctrine).

    ``total_content_views`` plays the part ``total_checkins`` does: shipped rather
    than left to be summed, so the buckets have something to reconcile *against*
    and a ref the API failed to emit shows up as a gap instead of silently
    redefining the denominator.

    ``guide_sessions`` is a structural 0 today — the conversational guide is US-16
    and nothing writes a GuideSession yet. It is reported rather than omitted for
    the same reason AttendanceReportOut reports ``staff: 0``: the zero says the
    guide FR-F3 anticipates is not yet wired, which an admin should be able to
    read off the report rather than infer from a missing field. A count, not a
    list, because there is nothing to break it down *by* — a chat has no ref.
    """

    challenge: ReportChallengeOut
    total_content_views: int
    content_views: list[ContentRefCountOut]
    guide_sessions: int


class OutcomeScoreOut(BaseModel):
    """How one learning outcome scored across the cohort (FR-F4 / US-24).

    ``outcome_tag`` is a plain str, and deliberately not a Literal reused from
    somewhere else — the trick MethodCountOut and ContentRefCountOut play, where
    reusing the write path's vocabulary makes a fourth method or a third content
    ref fail to validate here, cannot work for a vocabulary the admin authors.
    An outcome tag is free text on AssessmentItem (US-12), so there is nothing to
    reuse and no fixed set to check against: this report's buckets are whatever
    the challenge's items are tagged with.

    ``mean_score`` is the aggregate FR-F4 asks for, left as a raw 0.0..1.0 float.
    Rendering it as "84%" is the client's job — the same division of labour that
    keeps the auto *share* out of AttendanceReportOut.

    ``mean_score`` is None, never 0.0, exactly when ``response_count`` is 0. A
    tagged item nobody has answered has no mean, and 0.0 would claim the cohort
    scored zero on it — a lie where None is a blank. The tag still appears: see
    services/reports.py for why the query outer-joins to keep it.

    ``response_count`` is what the mean was taken over, and it is not decoration.
    A tag answered by two students and one answered by two hundred otherwise
    render identically, and an admin acting on an 84% owes the difference.

    ``human_scored_count`` is a structural 0 today — US-19's reflection override
    is what writes scored_by="human" and it has not shipped. Reported rather than
    omitted for the reason AttendanceReportOut reports ``staff: 0``: the zero says
    the override path FR-F4 anticipates is not yet wired, and it makes "human
    scores are included in the totals" readable off the report instead of a
    promise the reader has to take on faith.
    """

    outcome_tag: str
    mean_score: float | None
    response_count: int
    human_scored_count: int


class LearningOutcomeReportOut(BaseModel):
    """Mean assessment score per learning-outcome tag (FR-F4 / US-24).

    The report that replaces hand-scoring: every score a student has earned,
    grouped by the outcome its item is tagged to.

    There is no OUTCOME_ORDER constant to seed the buckets from, unlike
    METHOD_ORDER and CONTENT_REF_ORDER above. Those close over a vocabulary the
    code owns; this one is admin-authored per challenge, so the fixed order the
    other reports get from a module-level tuple comes from the query's ORDER BY
    instead (alphabetical by tag — see services/reports.py).

    ``total_responses`` and ``mean_score`` play the part ``total_checkins`` does:
    shipped so the buckets have something to reconcile *against*, and counted
    across every row rather than derived from the buckets. The total mean is
    response-weighted — the mean of every score, not the mean of the per-tag
    means, which differ whenever the tags have unequal counts. Weighting is the
    honest one: it answers "how did the cohort do", where a mean of means would
    let an outcome with three responses outvote one with three hundred.

    Aggregate only, no per-student rows (FR-F6) — the scores are academic
    performance, which is exactly what that rule exists to keep out of a
    dashboard.
    """

    challenge: ReportChallengeOut
    total_responses: int
    mean_score: float | None
    total_human_scored: int
    outcomes: list[OutcomeScoreOut]
