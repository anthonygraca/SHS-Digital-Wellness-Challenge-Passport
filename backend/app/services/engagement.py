"""Recording engagement (FR-F3 / US-23) — the write side of the report.

The counterpart to services/reports.py::engagement_report. Every other report in
this app reads rows some other feature wrote for its own reasons; this one has to
write its own, because nothing else has any reason to record that a student read
something.

Two entry points for two callers who know different amounts. The scan route
already holds a resolved Task, so re-deriving it from a week number would be a
second query and a second chance to disagree. The content-view route holds only
what a student's browser told it, so it resolves — and that resolution *is* the
campus check.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.challenge import Task
from app.models.engagement import ContentView
from app.schemas.engagement import ContentRef
from app.services.challenges import get_active_challenge_for_campus


def record_content_view_for_task(
    db: Session, *, student_id: int, task: Task, content_ref: ContentRef
) -> ContentView:
    """Record a view of content belonging to an already-resolved task.

    The caller vouches for the task — that it exists, and that it belongs to this
    student's campus. Only routers/passport.py's scan path uses this, and it holds
    a Task that record_event_qr_checkin already validated against the campus's
    active challenge.
    """
    view = ContentView(student_id=student_id, task_id=task.id, content_ref=content_ref)
    db.add(view)
    db.commit()
    return view


def record_content_view(
    db: Session, *, campus_id: str, student_id: int, week_no: int, content_ref: ContentRef
) -> ContentView | None:
    """Record a view of a week's content, resolving the week for the caller.

    Returns None when the campus has no active challenge or no week sits at
    ``week_no`` — the route turns that into a 404. Resolving against the campus's
    own active challenge is the isolation boundary: a student cannot post a view
    of a week that is not theirs to see, whatever number they send.

    Mirrors record_manual_checkin's resolution step, including the ``.first()``:
    positions are kept gapless and unique by the reorder service but no DB
    constraint enforces it, and a duplicate must not turn this into a 500.
    """
    challenge = get_active_challenge_for_campus(db, campus_id)
    if challenge is None:
        return None

    task = (
        db.execute(
            select(Task)
            .where(Task.challenge_id == challenge.id, Task.position == week_no)
            .order_by(Task.id)
        )
        .scalars()
        .first()
    )
    if task is None:
        return None

    return record_content_view_for_task(
        db, student_id=student_id, task=task, content_ref=content_ref
    )
