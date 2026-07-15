from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Challenge(Base):
    """An admin-authored challenge for a given semester (FR-B1).

    Starts in "draft" status; transitions to "published" when the admin
    explicitly publishes. Campus isolation is enforced by campus_id on every
    row — no campus can touch another's challenges.

    Only a "published" challenge is visible to students in their passport (US-5);
    "draft" is admin-only, still being authored.
    """

    __tablename__ = "challenges"
    __table_args__ = (
        UniqueConstraint(
            "campus_id",
            "name",
            "semester",
            name="uq_challenge_campus_name_sem",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campus_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    semester: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Drives the passport's visual theme (US-5). Empty string = default theme.
    theme_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    # "draft" | "published"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    tasks: Mapped[list[Task]] = relationship(
        "Task",
        back_populates="challenge",
        order_by="Task.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Task(Base):
    """An ordered weekly task within a challenge (FR-B2).

    `position` is the 1-based display order. Reordering is done by updating
    positions in a single service call so the order stays gapless. The passport
    (US-5) surfaces `position` as the week number and derives status from it by
    sequential unlock.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True
    )

    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    date_window_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    prize: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    challenge: Mapped[Challenge] = relationship("Challenge", back_populates="tasks")
    assessment_items: Mapped[list[AssessmentItem]] = relationship(
        "AssessmentItem",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


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
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Enrollment(Base):
    """A student's enrollment in a challenge (FR-C1 / US-3).

    Links a student to the challenge they joined. The composite unique
    constraint on (student_id, challenge_id) makes enrollment idempotent — a
    student cannot enroll in the same challenge twice.
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "challenge_id",
            name="uq_enrollment_student_challenge",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class AssessmentItem(Base):
    """An assessment item attached to a task (FR-B3).

    Supports two item types:
    - ``mcq``        — multiple-choice question with an answer key
    - ``reflection`` — open-ended prompt with a grading rubric

    Each item is tagged to a learning outcome (``outcome_tag``) for later
    aggregate reporting.
    """

    __tablename__ = "assessment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # "mcq" | "reflection"
    item_type: Mapped[str] = mapped_column(String(16), nullable=False)

    # Shared fields
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    outcome_tag: Mapped[str] = mapped_column(String(255), nullable=False)

    # MCQ-specific: ordered list of option strings, e.g. ["A", "B", "C", "D"]
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # MCQ-specific: the correct answer, e.g. "B"
    answer_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reflection-specific: free-text rubric used for grading
    rubric: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    task: Mapped[Task] = relationship("Task", back_populates="assessment_items")
