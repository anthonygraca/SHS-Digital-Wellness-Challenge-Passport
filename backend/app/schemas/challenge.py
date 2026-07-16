from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.services.qr import mint_event_token

# ---------------------------------------------------------------------------
# Assessment item schemas (FR-B3)
# Defined first so TaskOut can reference AssessmentItemOut without a forward ref.
# ---------------------------------------------------------------------------


class MCQCreate(BaseModel):
    """Payload for attaching a multiple-choice question."""

    item_type: Literal["mcq"]
    prompt: str
    outcome_tag: str
    options: list[str] = Field(..., min_length=2)
    answer_key: str

    @model_validator(mode="after")
    def answer_key_in_options(self) -> MCQCreate:
        if self.answer_key not in self.options:
            raise ValueError("answer_key must be one of the provided options")
        return self


class ReflectionCreate(BaseModel):
    """Payload for attaching a reflection item."""

    item_type: Literal["reflection"]
    prompt: str
    outcome_tag: str
    rubric: str


# Discriminated union — ``item_type`` selects the concrete model.
AssessmentItemCreate = Annotated[
    Union[MCQCreate, ReflectionCreate],
    Field(discriminator="item_type"),
]


class AssessmentItemUpdate(BaseModel):
    """Partial update — all fields optional; validation mirrors create rules."""

    prompt: str | None = None
    outcome_tag: str | None = None
    # MCQ
    options: list[str] | None = None
    answer_key: str | None = None
    # Reflection
    rubric: str | None = None

    @model_validator(mode="after")
    def answer_key_in_options_if_both_provided(self) -> AssessmentItemUpdate:
        if self.answer_key is not None and self.options is not None:
            if self.answer_key not in self.options:
                raise ValueError("answer_key must be one of the provided options")
        return self


class AssessmentItemOut(BaseModel):
    id: int
    task_id: int
    item_type: str
    prompt: str
    outcome_tag: str
    options: list[str] | None
    answer_key: str | None
    rubric: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    title: str
    caption: str = ""
    activity_type: str = ""
    location: str = ""
    date_window_start: date | None = None
    date_window_end: date | None = None
    prize: str = ""
    required: bool = True

    @model_validator(mode="after")
    def end_after_start(self) -> TaskCreate:
        if (
            self.date_window_start is not None
            and self.date_window_end is not None
            and self.date_window_end < self.date_window_start
        ):
            raise ValueError("date_window_end must be on or after date_window_start")
        return self


class TaskUpdate(BaseModel):
    title: str | None = None
    caption: str | None = None
    activity_type: str | None = None
    location: str | None = None
    date_window_start: date | None = None
    date_window_end: date | None = None
    prize: str | None = None
    required: bool | None = None


class TaskOut(BaseModel):
    id: int
    challenge_id: int
    position: int
    title: str
    caption: str
    activity_type: str
    location: str
    date_window_start: date | None
    date_window_end: date | None
    prize: str
    required: bool
    created_at: datetime
    updated_at: datetime
    # Populated lazily — empty list when no items have been attached.
    assessment_items: list[AssessmentItemOut] = []

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def qr_token(self) -> str:
        """Static signed token the admin dashboard renders as the event QR (US-8).

        Derived, never stored: the student scans this and POSTs it to
        ``/api/checkins/scan`` to record an ``event_qr`` check-in.
        """
        return mint_event_token(self.id)


class TaskReorder(BaseModel):
    """Ordered list of task IDs representing the desired new positions.

    The server assigns position = index + 1, so the list must contain
    exactly the IDs that already belong to the challenge.
    """

    task_ids: list[int]

    @field_validator("task_ids")
    @classmethod
    def no_duplicates(cls, v: list[int]) -> list[int]:
        if len(v) != len(set(v)):
            raise ValueError("task_ids must not contain duplicates")
        return v


# ---------------------------------------------------------------------------
# Challenge schemas
# ---------------------------------------------------------------------------


class ChallengeCreate(BaseModel):
    name: str
    semester: str
    start_date: date
    end_date: date
    # Re-skin preset (FR-B4). Empty string = default theme.
    theme_id: str = ""

    @model_validator(mode="after")
    def end_after_start(self) -> ChallengeCreate:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ChallengeUpdate(BaseModel):
    name: str | None = None
    semester: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    # "" resets to the default theme; omitted leaves the current one in place.
    theme_id: str | None = None


class ChallengeDuplicate(BaseModel):
    """Optional overrides for the copy (FR-B6).

    Both fields are optional so a bare ``POST .../duplicate`` works: the server
    derives a unique "<name> (Copy)" and reuses the original's semester. The
    admin UI supplies both so the copy lands on the semester it is being
    authored for.
    """

    name: str | None = None
    semester: str | None = None


class ChallengeOut(BaseModel):
    id: int
    campus_id: str
    name: str
    semester: str
    start_date: date
    end_date: date
    theme_id: str
    status: str
    tasks: list[TaskOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChallengeSummary(BaseModel):
    """Lightweight list-view representation (no tasks payload)."""

    id: int
    campus_id: str
    name: str
    semester: str
    start_date: date
    end_date: date
    theme_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Manual completion override + audit (FR-D6)
# ---------------------------------------------------------------------------

CheckInMethod = Literal["event_qr", "staff", "manual"]


def _nonblank(v: str) -> str:
    """Reject whitespace-only input.

    Field(min_length=1) accepts "   " — this is what makes the 422 real.
    """
    stripped = v.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class ManualCheckInCreate(BaseModel):
    """Admin marks a student complete for a task (FR-D6).

    The student is addressed by ``student_subject`` (their SSO subject) because
    the Student model deliberately stores no name or campus ID to search by.
    """

    student_subject: str = Field(..., min_length=1, max_length=255)
    reason: str = Field(..., min_length=1, max_length=1000)
    # Defaults to now. Lets an admin backdate a completion to when it happened.
    ts: datetime | None = None

    @field_validator("student_subject", "reason")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        return _nonblank(v)


class CheckInCorrect(BaseModel):
    """Correct an existing check-in.

    The student cannot be changed here — reassigning is a remove + create, which
    is two audit rows and the honest description of what happened.
    """

    reason: str = Field(..., min_length=1, max_length=1000)
    method: CheckInMethod | None = None
    ts: datetime | None = None

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        return _nonblank(v)


class CheckInRemove(BaseModel):
    """Remove a check-in. A reason is required even to delete."""

    reason: str = Field(..., min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        return _nonblank(v)


class CheckInOut(BaseModel):
    """A check-in as the admin sees it.

    No from_attributes: ``student_subject`` lives on the Student row, so this is
    assembled explicitly rather than read off a single ORM object.
    """

    id: int
    # int on the SQL path, "<campus>#<sso>" on the Dynamo path — the seam's declared
    # StudentId (repositories/base.py). Opaque either way: no UI reads it, and the
    # admin-facing identifier is student_subject below.
    student_id: int | str
    student_subject: str
    task_id: int
    ts: datetime
    method: str
    verified_by: str | None


class AssessmentResponseOut(BaseModel):
    """A student's scored response as the admin sees it (FR-E5).

    No from_attributes, for the same reason as ``CheckInOut``: ``student_subject`` lives
    on the Student row, so this is assembled explicitly.

    ``student_id`` and ``student_subject`` are the only identifiers here because they
    are the only ones that exist — ``Student`` carries no name and no campus ID number.
    The schema is the privacy guarantee, and this surface adds nothing to it.
    """

    id: int
    # See CheckInOut.student_id — int on SQL, "<campus>#<sso>" on Dynamo.
    student_id: int | str
    student_subject: str
    response: str
    score: float
    scored_by: str
    ai_feedback: str | None
    ts: datetime


class AssessmentScoreOverride(BaseModel):
    """Set a response's score by hand (FR-E5). ``scored_by`` becomes "human".

    Bounds are enforced here rather than in the service because this value comes from a
    form: an admin who types 5 meant 0.5 or made a mistake, and either way a 422 naming
    the range is more use than a silently clamped 1.0 skewing the FR-F4 mean.
    """

    score: float = Field(..., ge=0.0, le=1.0)


class CheckInAuditOut(BaseModel):
    """One row of the append-only audit ledger (FR-D6)."""

    id: int
    campus_id: str
    # See CheckInOut.student_id — int on SQL, "<campus>#<sso>" on Dynamo.
    student_id: int | str
    task_id: int
    checkin_id: int | None
    action: str
    actor_subject: str
    reason: str
    ts: datetime
    prior_state: dict | None
    new_state: dict | None

    model_config = {"from_attributes": True}
