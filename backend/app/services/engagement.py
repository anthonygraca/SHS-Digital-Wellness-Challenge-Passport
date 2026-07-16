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

Persistence-agnostic: both take a ``Repository``, so the resolution rule above runs
identically on either backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.schemas.engagement import ContentRef

if TYPE_CHECKING:
    from app.repositories.base import Repository, StudentId


def record_content_view_for_task(
    repo: Repository, *, student_id: StudentId, task, content_ref: ContentRef
) -> None:
    """Record a view of content belonging to an already-resolved task.

    The caller vouches for the task — that it exists, and that it belongs to this
    student's campus. Only routers/passport.py's scan path uses this, and it holds
    a Task that record_event_qr_checkin already validated against the campus's
    active challenge.
    """
    repo.record_content_view(student_id=student_id, task=task, content_ref=content_ref)


def record_content_view(
    repo: Repository,
    *,
    campus_id: str,
    student_id: StudentId,
    week_no: int,
    content_ref: ContentRef,
) -> bool:
    """Record a view of a week's content, resolving the week for the caller.

    Returns False when the campus has no active challenge or no week sits at
    ``week_no`` — the route turns that into a 404. Resolving against the campus's
    own active challenge is the isolation boundary: a student cannot post a view
    of a week that is not theirs to see, whatever number they send.
    """
    challenge = repo.get_active_challenge(campus_id)
    if challenge is None:
        return False

    task = repo.get_task_by_position(challenge.id, week_no)
    if task is None:
        return False

    repo.record_content_view(student_id=student_id, task=task, content_ref=content_ref)
    return True
