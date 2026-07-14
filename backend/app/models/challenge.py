from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Challenge(Base):
    """A themed multi-week wellness challenge (architecture-plan.md §5).

    A challenge is *data/config*, not code: an admin authors the weeks, dates, and
    theme per semester (FR-B). Scoped by ``campus_id`` for multi-tenancy (FR-A5).
    """

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campus_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    theme_id: Mapped[str] = mapped_column(String(64), nullable=False)
    semester: Mapped[str] = mapped_column(String(64), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class Task(Base):
    """One week/task within a challenge — the passport "tiles" (architecture-plan.md §5).

    Ordered by ``week_no``. ``is_required`` drives prize eligibility (US-7); the date
    window is display metadata for US-5 (status is derived by sequential unlock).
    """

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("challenge_id", "week_no", name="uq_task_challenge_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id"), nullable=False, index=True
    )
    week_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    caption: Mapped[str] = mapped_column(String(1024), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    prize: Mapped[str] = mapped_column(String(255), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CheckIn(Base):
    """A recorded task completion (architecture-plan.md §5, FR-D4).

    US-5 only *reads* these to derive week status and the countdown; the scan/validate
    write path is US-8. ``method`` is one of ``event_qr`` / ``staff`` / ``manual``. The
    unique pair prevents a week being completed twice.
    """

    __tablename__ = "checkins"
    __table_args__ = (
        UniqueConstraint("student_id", "task_id", name="uq_checkin_student_task"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
