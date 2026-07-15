from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import (
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


class CheckInMethod(str, Enum):
    """Method used for check-in (US-8, US-15)."""

    EVENT_QR = "event_qr"
    STAFF = "staff"
    MANUAL = "manual"


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

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="challenge",
        order_by="Task.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        "Enrollment",
        back_populates="challenge",
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

    # SHS-approved content reference for grounding AI tips (US-15, FR-E1)
    content_tags: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    challenge: Mapped["Challenge"] = relationship("Challenge", back_populates="tasks")
    checkins: Mapped[list["CheckIn"]] = relationship(
        "CheckIn",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    assessment_items: Mapped[list["AssessmentItem"]] = relationship(
        "AssessmentItem",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Enrollment(Base):
    """Student enrollment in a challenge (FR-C1, US-15).

    Students must enroll before checking in. One enrollment per student per challenge.
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "challenge_id", name="uq_enrollment"),
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

    challenge: Mapped["Challenge"] = relationship("Challenge", back_populates="enrollments")


class CheckIn(Base):
    """A student's completion of a task (FR-D1, FR-D2, FR-D4, US-8, US-15).

    Records who, what task, when, and how (event_qr / staff / manual).
    Triggers personalized tip generation (US-15).
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
    # Method: "event_qr", "staff", or "manual"
    method: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    checked_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    # For staff-verified check-ins (method=staff or manual)
    verified_by: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True
    )

    task: Mapped["Task"] = relationship("Task", back_populates="checkins")


class AssessmentItem(Base):
    """An assessment item attached to a task (FR-B3).

    Supports two item types:
    - ``mcq``       — multiple-choice question with an answer key
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
    outcome_tag: Mapped[str] = mapped_column(String(64), nullable=False)

    # MCQ fields (null for reflection)
    mcq_options: Mapped[str | None] = mapped_column(Text, nullable=True)
    mcq_answer_key: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Reflection fields (null for mcq)
    reflection_rubric: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    task: Mapped["Task"] = relationship("Task", back_populates="assessment_items")
