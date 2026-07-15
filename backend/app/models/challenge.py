from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
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


class AssessmentResponse(Base):
    """A student's answer to an assessment item, with its score (FR-E4).

    architecture-plan.md §5 calls this ``QuizResponse``; the implemented item model
    is ``AssessmentItem``, so the name follows the code.

    The learning-outcome tag is reached by joining ``item``, never copied here.
    ``CheckInAudit`` below denormalizes for a reason that does not apply to this
    table: it carries no foreign keys and must outlive the rows it describes,
    whereas a response cannot outlive its item (the FK cascades). Copying the tag
    would instead fork history — an admin editing ``AssessmentItem.outcome_tag``
    (US-12) would leave old responses filed under the old tag, so the FR-F4
    per-outcome report would count one item under two tags with no right answer.
    Joining means retagging an item retags its whole score history, which is what
    retagging an item means.

    The unique pair makes an MCQ one attempt, mirroring ``CheckIn`` above. That is
    load-bearing rather than tidy: the FR-E4 feedback names the correct option, so
    without it "answer wrong, read the answer, answer again" would make every
    stored score a 1.0 and the FR-F4 aggregate a flat line.
    """

    __tablename__ = "assessment_responses"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "assessment_item_id", name="uq_response_student_item"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_item_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The chosen option string for an MCQ; the essay text for a reflection (US-19).
    response: Mapped[str] = mapped_column(Text, nullable=False)

    # 0.0..1.0. Float rather than Integer because FR-F4 aggregates a *mean* per
    # outcome tag, and US-19's rubric scoring is fractional — one column serves both.
    score: Mapped[float] = mapped_column(Float, nullable=False)

    # "auto" | "human". Always "auto" on this branch; US-19's admin override writes
    # "human". Present now because the column is NOT NULL and there is no Alembic —
    # adding it later would mean dropping every existing database.
    scored_by: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    item: Mapped[AssessmentItem] = relationship("AssessmentItem")


class CheckInAudit(Base):
    """An append-only ledger of an admin's manual completion change (FR-D6).

    ``CheckIn`` remains the single source of truth for "is this complete?"; this
    table records *who* changed it, *when*, *why*, and *what it looked like
    before*. Rows are only ever inserted — never updated or deleted.

    Deliberately NOT foreign-keyed to checkins / students / tasks. A ``checkins``
    row is hard-deleted when an admin removes a completion, and both ``students``
    and ``tasks`` cascade-delete their dependents — so an FK here could only
    cascade (destroying the very evidence FR-D6 exists to guarantee) or SET NULL
    (losing the correlation). RESTRICT would preserve the ledger but block
    legitimate task deletion. Instead the ledger carries self-contained snapshots
    and plain indexed integers, so it outlives anything it points at.
    """

    __tablename__ = "checkin_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Denormalized from the challenge so audit reads stay campus-isolated even
    # after the referenced task is gone.
    campus_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Plain integers, not FKs — see the class docstring.
    student_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # The checkin row's id at the time of the action. A correlation hint only:
    # SQLite reuses rowids, so a later check-in may reappear under the same id.
    checkin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # "create" | "update" | "delete"
    action: Mapped[str] = mapped_column(String(16), nullable=False)

    # The acting admin's SSO subject (session claims["sub"]). No name, no PHI —
    # the same privacy guarantee the Student model makes.
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    # Required and non-blank; enforced at the schema layer.
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    # Full snapshots of the check-in either side of the change. prior_state is
    # None for "create"; new_state is None for "delete". Datetimes are stored
    # ISO-8601 — the JSON column cannot serialize a datetime.
    prior_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
