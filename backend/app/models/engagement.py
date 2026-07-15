from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContentView(Base):
    """A student looking at a piece of content — the engagement metric (FR-F3 / US-23).

    Built as architecture-plan.md:144 reserved it: ``(student_id, task_id,
    content_ref, ts)``. ``content_ref`` says *which* content, and is the only
    thing separating the two things a student can look at today: the week detail
    sheet (``week_detail``) and the post-check-in tip (``tip``). See
    schemas/engagement.py for the vocabulary.

    The first write-side instrumentation in the app. Every other report counts
    rows some other feature already wrote for its own reasons — a check-in exists
    whether or not anyone reports on it. A view exists *only* because this table
    is here, which is why the write paths are part of US-23 rather than assumed.

    No unique constraint on (student_id, task_id, content_ref), unlike
    ``uq_checkin_student_task``. A week can only be *completed* once, but it can
    be *read* any number of times, and re-reading is engagement rather than a
    duplicate to reject. That makes the grain the same one attendance_report
    documents: this counts views, not viewers.

    Scoped through ``task_id`` rather than carrying ``challenge_id``, exactly as
    CheckIn is: the join through Task is what keeps another campus's rows out of
    a report (services/reports.py). Inheriting the shape means inheriting the
    isolation the reporting layer already knows how to enforce.
    """

    __tablename__ = "content_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_ref: Mapped[str] = mapped_column(String(32), nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class GuideSession(Base):
    """One student's conversation with the wellness guide (FR-F3 / US-23).

    Nothing writes this table yet: the guide itself is US-16, and until it lands
    the engagement report counts a structural zero here. That zero is reported
    rather than hidden, for the same reason AttendanceReportOut ships a ``staff``
    bucket that is always 0 — it says the capture path FR-F3 anticipates is not
    yet wired, which is a finding, not an absence.

    ``challenge_id`` directly, where ContentView above reaches its challenge
    through ``task_id``. A chat is not about a week — a student can ask the guide
    anything at any point in the semester — so there is no task to inherit the
    scope from, and the report needs *some* column to group by.
    """

    __tablename__ = "guide_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
