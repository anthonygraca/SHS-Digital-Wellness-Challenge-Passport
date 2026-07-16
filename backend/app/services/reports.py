"""Reporting over a challenge (UC-10 / FR-F1, FR-F2, FR-F3, FR-F4, FR-F5).

Read-only and cohort-wide, which is what separates this from passport.py: that
module derives one student's progress, this one reads across all of them. Both
answer "is this week complete?" the same way — a CheckIn row for the week's Task
— so the funnel and a student's own passport can never disagree.

Persistence-agnostic: every function takes a ``Repository`` and a resolved challenge,
never a Session. The repository supplies the challenge-scoped bulk reads; the
*aggregation* — distinct students vs raw captures, the outer join that keeps a zero
week or tag visible, the eligibility rule — lives here, defined once for both backends.

Nothing is cached or stored: every request re-derives the answer, so a check-in
recorded a second ago is in the next refresh (US-21, scenario 2) and in the next
export (US-26, scenario 2). On DynamoDB the dashboards read a GSI, which lags the base
table by well under a second; the prize export cannot tolerate even that (real prizes),
so it alone reads strongly-consistent — see ``prize_eligible_students``.

participation_report, attendance_report, engagement_report and
learning_outcome_report are aggregate (FR-F6); prize_eligible_students is the one
per-student read here, because a drawing list has to name its entrants.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from app.schemas.report import (
    CONTENT_REF_ORDER,
    METHOD_ORDER,
    AttendanceReportOut,
    ContentRefCountOut,
    EngagementReportOut,
    LearningOutcomeReportOut,
    MethodCountOut,
    OutcomeScoreOut,
    ParticipationReportOut,
    PrizeEligibleRow,
    ReportChallengeOut,
    WeekCompletionOut,
)

if TYPE_CHECKING:
    from app.repositories.base import Repository


def _mean(scores: list[float]) -> float | None:
    """Mean over the rows, or None over none.

    Computed across every response, never folded up from per-tag means: averaging
    the means would weight a tag with three responses the same as one with three
    hundred, which is a different — and wrong — answer to "how did the cohort do".
    """
    return sum(scores) / len(scores) if scores else None


def participation_report(repo: Repository, challenge) -> ParticipationReportOut:
    """Total enrollments plus the per-week completion funnel for one challenge.

    count(distinct student_id) rather than count(*): uq_checkin_student_task already
    makes those equal, but the funnel counts *students*, and building the per-task set
    of student ids keeps that honest if the constraint ever loosens.

    Every task appears, even one nobody has finished — the Python analogue of the SQL
    LEFT OUTER JOIN — otherwise the drop-off the report exists to show would vanish.
    """
    tasks = repo.list_challenge_tasks(challenge.id)
    checkins = repo.list_challenge_checkins(challenge.id)

    students_by_task: dict[int, set] = defaultdict(set)
    for c in checkins:
        students_by_task[c.task_id].add(c.student_id)

    return ParticipationReportOut(
        challenge=ReportChallengeOut.model_validate(challenge),
        total_enrollments=repo.count_enrollments(challenge.id),
        weeks=[
            WeekCompletionOut(
                task_id=t.id,
                week_no=t.position,
                title=t.title,
                required=t.required,
                completed_count=len(students_by_task.get(t.id, ())),
            )
            for t in tasks
        ],
    )


def attendance_report(repo: Repository, challenge) -> AttendanceReportOut:
    """Check-in counts broken down by capture method for one challenge (FR-F2).

    count(*), not count(distinct student_id) as the funnel uses: this counts
    *captures*, not students. One student scanning six weeks is six units of effort
    the system saved, and six is the honest number.

    All three buckets are shown even at zero — "staff: 0" is a finding (nothing writes
    that method today), not an absence to hide — and the total counts every row rather
    than summing the buckets, so a method outside CheckInMethod would surface as a gap
    in the reconciliation rather than being silently dropped.
    """
    checkins = repo.list_challenge_checkins(challenge.id)

    counts = dict.fromkeys(METHOD_ORDER, 0)
    for c in checkins:
        if c.method in counts:
            counts[c.method] += 1

    return AttendanceReportOut(
        challenge=ReportChallengeOut.model_validate(challenge),
        total_checkins=len(checkins),
        methods=[
            MethodCountOut(method=method, count=count) for method, count in counts.items()
        ],
    )


def engagement_report(repo: Repository, challenge) -> EngagementReportOut:
    """Content views and guide sessions for one challenge (FR-F3 / US-23).

    count(*), not count(distinct student_id): this counts *views*, not viewers. A
    student who opens the same week twice engaged twice. Every ref is shown, always,
    in a fixed order — the same guarantee the method buckets make.
    """
    view_counts = repo.count_content_views(challenge.id)

    counts = dict.fromkeys(CONTENT_REF_ORDER, 0)
    for content_ref, count in view_counts.items():
        if content_ref in counts:
            counts[content_ref] = count

    # Total over every recorded view, including a ref outside ContentRef (a write-path
    # bug), so it surfaces as a reconciliation gap rather than being hidden.
    total_content_views = sum(view_counts.values())

    return EngagementReportOut(
        challenge=ReportChallengeOut.model_validate(challenge),
        total_content_views=total_content_views,
        content_views=[
            ContentRefCountOut(content_ref=content_ref, count=count)
            for content_ref, count in counts.items()
        ],
        guide_sessions=repo.count_guide_sessions(challenge.id),
    )


def learning_outcome_report(repo: Repository, challenge) -> LearningOutcomeReportOut:
    """Mean assessment score per learning-outcome tag (FR-F4 / US-24).

    The tag lives on the item and is reached through it, never copied onto the response
    (models/challenge.py: copying would fork history, and retagging an item would leave
    old scores under the old tag). So the grouping key comes from the items.

    Driven from the item tag set with an **outer** join to the responses, not from the
    responses inward: a tag whose items nobody has answered yet must still appear, as
    response_count 0 and mean_score None. Seeding the buckets from the challenge's own
    items is what makes "nobody has answered anything tagged sleep-hygiene" a finding
    the report states rather than a row it silently omits.

    No filter on scored_by: a human-overridden score is a score (US-24 scenario 2). It
    is counted separately as well as included, so the aggregate can be read without
    taking that on faith.
    """
    items = repo.list_challenge_items(challenge.id)
    responses = repo.list_challenge_responses(challenge.id)

    tag_by_item = {item.id: item.outcome_tag for item in items}
    # Seed every tag the challenge's items carry, so an unanswered tag is a zero row.
    scores_by_tag: dict[str, list[float]] = {tag: [] for tag in tag_by_item.values()}
    human_by_tag: dict[str, int] = defaultdict(int)

    all_scores: list[float] = []
    total_human = 0
    for r in responses:
        tag = tag_by_item.get(r.assessment_item_id)
        if tag is None:
            continue  # a response whose item is gone — outside this report's scope
        scores_by_tag.setdefault(tag, []).append(r.score)
        all_scores.append(r.score)
        if r.scored_by == "human":
            human_by_tag[tag] += 1
            total_human += 1

    return LearningOutcomeReportOut(
        challenge=ReportChallengeOut.model_validate(challenge),
        total_responses=len(all_scores),
        mean_score=_mean(all_scores),
        total_human_scored=total_human,
        outcomes=[
            OutcomeScoreOut(
                outcome_tag=tag,
                mean_score=_mean(scores_by_tag[tag]),
                response_count=len(scores_by_tag[tag]),
                human_scored_count=human_by_tag.get(tag, 0),
            )
            # Alphabetical: there is no meaningful order to seed from, and two reads of
            # unchanged data agreeing is worth more than ranking by a mean that moves.
            for tag in sorted(scores_by_tag)
        ],
    )


def prize_eligible_students(repo: Repository, challenge) -> list[PrizeEligibleRow]:
    """Students who have completed every required task of one challenge (FR-F5 / US-26).

    The same rule passport.py derives for a single student, expressed set-wise for the
    whole cohort: restrict to the challenge's *required* tasks, then keep the students
    whose distinct completions cover all of them. Optional tasks fall out rather than
    being filtered later, so finishing or skipping one can never change eligibility.

    Reads strongly-consistent (``consistent=True``): the export is a record an admin
    acts on, and US-26 scenario 2 requires a student's final check-in to appear in an
    export run a moment later. A GSI cannot promise that; the base table can.

    No required tasks means nobody is eligible, not everybody — the guard passport.py
    also applies, so an all-optional challenge never exports the whole cohort for free.
    """
    required_ids = {t.id for t in repo.list_challenge_tasks(challenge.id) if t.required}
    if not required_ids:
        return []

    checkins = repo.list_challenge_checkins(challenge.id, consistent=True)

    completed: dict = defaultdict(set)
    eligible_since: dict = {}
    for c in checkins:
        if c.task_id not in required_ids:
            continue
        completed[c.student_id].add(c.task_id)
        # The latest check-in among the required set is when they qualified.
        if c.student_id not in eligible_since or c.ts > eligible_since[c.student_id]:
            eligible_since[c.student_id] = c.ts

    eligible_ids = [
        sid for sid, done in completed.items() if len(done) == len(required_ids)
    ]
    subjects = repo.get_student_subjects(eligible_ids)

    rows = [
        PrizeEligibleRow(
            student_id=sid,
            sso_subject=subjects.get(sid, ""),
            required_completed=len(completed[sid]),
            required_total=len(required_ids),
            eligible_since=eligible_since[sid],
        )
        for sid in eligible_ids
    ]
    # Ordered so two exports of unchanged data are byte-identical: the drawing list is a
    # record, and a diff between re-exports should mean something.
    rows.sort(key=lambda r: (r.eligible_since, str(r.student_id)))
    return rows
