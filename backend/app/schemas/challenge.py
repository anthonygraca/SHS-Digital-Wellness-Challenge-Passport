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


class ChallengeOut(BaseModel):
    id: int
    campus_id: str
    name: str
    semester: str
    start_date: date
    end_date: date
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
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
