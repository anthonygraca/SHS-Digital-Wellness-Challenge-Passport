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


class ChallengeStatus(str, Enum):
    """Challenge lifecycle states."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ActivityType(str, Enum):
    """Task activity categories."""

    EVENT = "event"
    CONTENT = "content"
    ASSESSMENT = "assessment"
    REFLECTION = "reflection"


class CheckInMethod(str, Enum):
    """How a check-in was recorded."""

    EVENT_QR = "event_qr"
    STAFF = "staff"
    MANUAL = "manual"


class Challenge(Base):
    """A themed wellness challenge for a campus semester (FR-B1, FR-B2).

    Each challenge has multiple weeks/tasks. Students enroll and complete tasks
    to become prize-eligible.
    """

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campus_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    theme_name: Mapped[str] = mapped_column(String(100), nullable=True)
    semester: Mapped[str] = mapped_column(String(50), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="challenge", cascade="all, delete-orphan"
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        "Enrollment", back_populates="challenge", cascade="all, delete-orphan"
    )


class Task(Base):
    """A week/activity within a challenge (FR-B3, FR-B4).

    Represents a single completable unit (e.g., "Week 3 - Vision Check").
    Tasks have date windows, locations, and prize requirements.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id"), nullable=False, index=True
    )
    week_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    challenge: Mapped["Challenge"] = relationship("Challenge", back_populates="tasks")
    check_ins: Mapped[list["CheckIn"]] = relationship(
        "CheckIn", back_populates="task", cascade="all, delete-orphan"
    )


class Enrollment(Base):
    """Student enrollment in a challenge (FR-C1).

    Records when a student joins a challenge. One student can enroll in multiple
    challenges (different semesters), but only once per challenge.
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "challenge_id", name="uq_enrollment_student_challenge"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id"), nullable=False, index=True
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    challenge: Mapped["Challenge"] = relationship("Challenge", back_populates="enrollments")


class CheckIn(Base):
    """A student's completion of a task (FR-D1, FR-D2, FR-D4).

    Records attendance/completion with timestamp, method (QR/staff/manual), and
    optional verifier. Prevents duplicate completions via uniqueness constraint.
    """

    __tablename__ = "check_ins"
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
    checked_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    verified_by: Mapped[int | None] = mapped_column(
        ForeignKey("students.id"), nullable=True
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="check_ins")
