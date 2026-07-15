"""Reporting over a challenge (UC-10 / FR-F1, FR-F2, FR-F3, FR-F4, FR-F5).

Read-only and cohort-wide, which is what separates this from passport.py: that
module derives one student's progress, this one reads across all of them. Both
answer "is this week complete?" the same way — a CheckIn row for the week's Task
— so the funnel and a student's own passport can never disagree.

Nothing is cached or stored: every request re-derives the answer, so a check-in
recorded a second ago is in the next refresh (US-21, scenario 2) and in the next
export (US-26, scenario 2).

participation_report, attendance_report, engagement_report and
learning_outcome_report are aggregate (FR-F6); prize_eligible_students is the one
per-student read here, because a drawing list has to name its entrants.

engagement_report is the one report whose rows exist only because it wants them:
check-ins and enrollments are written by features that would exist anyway, where
a ContentView is written by instrumentation US-23 added (services/engagement.py).
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.challenge import (
    AssessmentItem,
    AssessmentResponse,
    Challenge,
    CheckIn,
    Enrollment,
    Task,
)
from app.models.engagement import ContentView, GuideSession
from app.models.student import Student
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


def attendance_report(db: Session, challenge: Challenge) -> AttendanceReportOut:
    """Check-in counts broken down by capture method for one challenge (FR-F2).

    CheckIn carries no challenge_id, so the scope comes from a join through Task:
    a check-in belongs to the challenge its task belongs to. That join does here
    what the challenge_id filter does in participation_report — it is the only
    thing keeping another campus's check-ins out of the counts.

    count(*), not count(distinct student_id) as the funnel uses: this report
    counts *captures*, not students. One student scanning six weeks is six units
    of effort the system saved, and six is the honest number.
    """
    rows = db.execute(
        select(CheckIn.method, func.count().label("count"))
        .join(Task, Task.id == CheckIn.task_id)
        .where(Task.challenge_id == challenge.id)
        .group_by(CheckIn.method)
    ).all()

    # GROUP BY only emits methods that have rows, but the report owes the reader
    # all three buckets: "staff: 0" is a finding — nothing writes that method
    # today — not an absence to hide. Same reason the funnel keeps its zero
    # weeks. Seeding from METHOD_ORDER also fixes the order the client renders in.
    counts = dict.fromkeys(METHOD_ORDER, 0)
    for method, count in rows:
        if method in counts:
            counts[method] = count

    # Counted across every row, not summed from the buckets above. A method
    # outside CheckInMethod would be a write-path bug; a total that quietly
    # dropped it would hide the bug, where this makes it surface as a gap in the
    # reconciliation the report promises. No write path can mint one today.
    total_checkins = sum(count for _, count in rows)

    return AttendanceReportOut(
        challenge=ReportChallengeOut.model_validate(challenge),
        total_checkins=total_checkins,
        methods=[
            MethodCountOut(method=method, count=count) for method, count in counts.items()
        ],
    )


def engagement_report(db: Session, challenge: Challenge) -> EngagementReportOut:
    """Content views and guide sessions for one challenge (FR-F3 / US-23).

    Two counts from two tables, because the two things engage differently.
    ContentView carries no challenge_id and is scoped by the join through Task —
    the same join, for the same reason, as attendance_report's. GuideSession
    carries challenge_id directly: a chat is not about a week, so there is no task
    to inherit the scope from.

    count(*), not count(distinct student_id), like the attendance report and
    unlike the funnel: this counts *views*, not viewers. A student who opens the
    same week on Monday and again on Friday engaged twice, and two is the honest
    number.
    """
    rows = db.execute(
        select(ContentView.content_ref, func.count().label("count"))
        .join(Task, Task.id == ContentView.task_id)
        .where(Task.challenge_id == challenge.id)
        .group_by(ContentView.content_ref)
    ).all()

    # Every ref, always, in a fixed order — the same guarantee the method buckets
    # make. "tip: 0" is a finding (nobody has scanned yet), not an absence to hide.
    counts = dict.fromkeys(CONTENT_REF_ORDER, 0)
    for content_ref, count in rows:
        if content_ref in counts:
            counts[content_ref] = count

    # Counted across every row rather than summed from the buckets, exactly as
    # attendance_report's total is: a ref outside ContentRef would be a write-path
    # bug, and a total that quietly dropped it would hide the bug where this makes
    # it surface as a gap in the reconciliation the report promises.
    total_content_views = sum(count for _, count in rows)

    guide_sessions = (
        db.scalar(
            select(func.count())
            .select_from(GuideSession)
            .where(GuideSession.challenge_id == challenge.id)
        )
        or 0
    )

    return EngagementReportOut(
        challenge=ReportChallengeOut.model_validate(challenge),
        total_content_views=total_content_views,
        content_views=[
            ContentRefCountOut(content_ref=content_ref, count=count)
            for content_ref, count in counts.items()
        ],
        guide_sessions=guide_sessions,
    )


def learning_outcome_report(
    db: Session, challenge: Challenge
) -> LearningOutcomeReportOut:
    """Mean assessment score per learning-outcome tag (FR-F4 / US-24).

    The tag lives on AssessmentItem and is reached by joining, never copied onto
    the response (models/challenge.py argues why: copying would fork history, and
    retagging an item would leave its old scores filed under the old tag). So the
    grouping key comes from the item, and the scores come from its responses.

    Scoped by a join through Task to challenge_id — the same join, for the same
    reason, as attendance_report's and engagement_report's, just one hop longer:
    a response belongs to the challenge its item's task belongs to. That join is
    the only thing keeping another campus's scores out of these means.

    Driven from AssessmentItem with an **outer** join to the responses, not from
    AssessmentResponse inward. This is the funnel's LEFT OUTER JOIN argument in
    another vocabulary: a tag whose items nobody has answered yet must still
    appear, as response_count 0 and mean_score None. The other two reports get
    that guarantee by seeding their buckets from a constant, which cannot work
    here — an outcome tag is admin-authored free text, so there is no constant to
    seed from. But the tag set is still knowable, because the challenge's own
    items enumerate it, and reading it off them is what makes "nobody has answered
    anything tagged sleep-hygiene" a finding the report states rather than a row
    it silently omits. An inner join would quietly describe only the answered
    tags, which is a different report than the one FR-F4 asks for.

    No filter on scored_by: a human-overridden score is a score, and including it
    is the whole of US-24's second scenario. It is counted separately as well as
    included, so the aggregate can be read without taking that on faith.
    """
    rows = db.execute(
        select(
            AssessmentItem.outcome_tag,
            func.count(AssessmentResponse.id).label("response_count"),
            func.avg(AssessmentResponse.score).label("mean_score"),
            func.sum(
                case((AssessmentResponse.scored_by == "human", 1), else_=0)
            ).label("human_scored_count"),
        )
        .select_from(AssessmentItem)
        .join(Task, Task.id == AssessmentItem.task_id)
        .outerjoin(
            AssessmentResponse,
            AssessmentResponse.assessment_item_id == AssessmentItem.id,
        )
        .where(Task.challenge_id == challenge.id)
        .group_by(AssessmentItem.outcome_tag)
        # Alphabetical, because there is no meaningful order to seed from and the
        # rows have to land somewhere fixed. Ordering by score instead would move
        # a row every time its mean ticked over a rounding boundary, so a card an
        # admin refreshes would reshuffle under them; the tag is stable, and two
        # reads of unchanged data agreeing is worth more here than ranking.
        .order_by(AssessmentItem.outcome_tag)
    ).all()

    # Counted across every response rather than folded up from the buckets, as
    # attendance_report's total is and for the same reason. The mean especially:
    # averaging the per-tag means would weight a tag with three responses the same
    # as one with three hundred, which is a different — and wrong — answer to
    # "how did the cohort do". avg() over every row weights by response, which is
    # the honest one. Over no rows it is NULL, and None is what the schema wants.
    total_responses, total_mean, total_human = db.execute(
        select(
            func.count(AssessmentResponse.id),
            func.avg(AssessmentResponse.score),
            func.sum(case((AssessmentResponse.scored_by == "human", 1), else_=0)),
        )
        .select_from(AssessmentResponse)
        .join(
            AssessmentItem,
            AssessmentItem.id == AssessmentResponse.assessment_item_id,
        )
        .join(Task, Task.id == AssessmentItem.task_id)
        .where(Task.challenge_id == challenge.id)
    ).one()

    return LearningOutcomeReportOut(
        challenge=ReportChallengeOut.model_validate(challenge),
        total_responses=total_responses or 0,
        mean_score=total_mean,
        # sum() over no rows is NULL, where count() is already 0.
        total_human_scored=total_human or 0,
        outcomes=[
            OutcomeScoreOut(
                outcome_tag=outcome_tag,
                mean_score=mean_score,
                response_count=response_count,
                human_scored_count=human_scored_count or 0,
            )
            for outcome_tag, response_count, mean_score, human_scored_count in rows
        ],
    )


def prize_eligible_students(db: Session, challenge: Challenge) -> list[PrizeEligibleRow]:
    """Students who have completed every required task of one challenge (FR-F5 / US-26).

    The same rule passport.py derives for a single student, expressed set-wise for
    the whole cohort: restrict to the challenge's *required* tasks, then keep the
    students whose distinct completions cover all of them. Optional tasks fall out
    of the query rather than being filtered later, which is why finishing or
    skipping one can never change eligibility.

    Derived per call, never stored — so an export run a second after a student's
    final check-in already contains them (US-26, scenario 2).
    """
    required_ids = list(
        db.execute(
            select(Task.id).where(
                Task.challenge_id == challenge.id, Task.required.is_(True)
            )
        ).scalars()
    )

    # No required tasks means nobody is eligible, not everybody: the same guard
    # passport.py applies (``required_total > 0``) so an all-optional challenge
    # never exports the whole cohort for free. Also avoids a HAVING count == 0.
    if not required_ids:
        return []

    # Enrollment is deliberately not joined. Passport eligibility doesn't consult
    # it either, and campus isolation already comes from the caller-resolved
    # challenge — joining it here could drop a student who has check-ins but no
    # enrollment row, making this export disagree with that student's own passport.
    #
    # The HAVING *is* the "completed every required task" rule: count(distinct
    # task_id) over the required set can only reach len(required_ids) when the
    # student has one check-in per required task.
    rows = db.execute(
        select(
            Student.id,
            Student.sso_subject,
            func.count(func.distinct(CheckIn.task_id)).label("required_completed"),
            func.max(CheckIn.ts).label("eligible_since"),
        )
        .join(CheckIn, CheckIn.student_id == Student.id)
        .where(CheckIn.task_id.in_(required_ids))
        .group_by(Student.id, Student.sso_subject)
        .having(func.count(func.distinct(CheckIn.task_id)) == len(required_ids))
        # Ordered so two exports of unchanged data are byte-identical: the drawing
        # list is a record, and a diff between re-exports should mean something.
        .order_by(func.max(CheckIn.ts), Student.id)
    ).all()

    return [
        PrizeEligibleRow(
            student_id=student_id,
            sso_subject=sso_subject,
            required_completed=required_completed,
            required_total=len(required_ids),
            eligible_since=eligible_since,
        )
        for student_id, sso_subject, required_completed, eligible_since in rows
    ]
