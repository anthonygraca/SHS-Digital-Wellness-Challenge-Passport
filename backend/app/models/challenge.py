"""Challenge, Task, Enrollment, and CheckIn models (FR-B1, FR-B2, FR-D1, FR-D4, FR-E1).

A Challenge contains ordered weekly Tasks. Students enroll in Challenges and
check in to Tasks. Check-ins trigger personalized tips (US-15).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
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
    """Challenge lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ActivityType(str, Enum):
    """Task activity types."""

    WORKSHOP = "workshop"
    SCREENING = "screening"
    LAB = "lab"
    SEMINAR = "seminar"
    EVENT = "event"


class CheckInMethod(str, Enum):
    """How a check-in was captured (FR-D4)."""

    EVENT_QR = "event_qr"  # Student scanned event QR
    STAFF = "staff"  # Staff scanned student's passport QR
    MANUAL = "manual"  # Admin manual override


class Challenge(Base):
    """A themed wellness challenge with ordered weekly tasks (FR-B1, FR-B2).

    Challenges are data/config, never code. Each challenge belongs to a campus
    and has a specific semester/date range.
    """

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campus_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    semester: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ChallengeStatus.DRAFT.value, index=True
    )
    theme_name: Mapped[str] = mapped_column(String(100), nullable=True)
    starts_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
    """A weekly task within a challenge (FR-B2).

    Each task has a title, caption, activity type, location, date window,
    prize description, and a required flag for prize eligibility.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("challenges.id"), nullable=False, index=True
    )
    week_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    date_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prize: Mapped[str] = mapped_column(String(255), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    # SHS-approved content reference for grounding AI tips (US-15, FR-E1)
    content_tags: Mapped[str] = mapped_column(String(255), nullable=True)

    # Relationships
    challenge: Mapped["Challenge"] = relationship("Challenge", back_populates="tasks")
    checkins: Mapped[list["CheckIn"]] = relationship(
        "CheckIn", back_populates="task", cascade="all, delete-orphan"
    )


class Enrollment(Base):
    """Student enrollment in a challenge (FR-C1).

    Students must enroll before checking in. One enrollment per student per challenge.
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "challenge_id", name="uq_enrollment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id"), nullable=False, index=True
    )
    challenge_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("challenges.id"), nullable=False, index=True
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Relationships
    challenge: Mapped["Challenge"] = relationship("Challenge", back_populates="enrollments")


class CheckIn(Base):
    """A student's completion of a task (FR-D1, FR-D2, FR-D4, US-8).

    Records who, what task, when, and how (event_qr / staff / manual).
    Triggers personalized tip generation (US-15).
    """

    __tablename__ = "checkins"
    __table_args__ = (
        UniqueConstraint("student_id", "task_id", name="uq_checkin_student_task"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id"), nullable=False, index=True
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tasks.id"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    checked_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    # For staff-verified check-ins (method=staff or manual)
    verified_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("students.id"), nullable=True
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="checkins")
