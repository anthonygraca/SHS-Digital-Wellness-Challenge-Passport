from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, field_validator, model_validator

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

    model_config = {"from_attributes": True}


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
