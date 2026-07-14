from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class WeekStatus(str, Enum):
    """Week/task status for passport display (FR-C2)."""

    LOCKED = "locked"
    AVAILABLE = "available"
    COMPLETE = "complete"


class TaskOut(BaseModel):
    """A task/week in the challenge with completion status."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    challenge_id: int
    week_no: int
    title: str
    caption: str | None
    activity_type: str
    location: str | None
    date_start: date
    date_end: date
    is_required: bool
    order: int
    status: WeekStatus


class ChallengeOut(BaseModel):
    """A challenge with basic metadata (no tasks)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: str
    name: str
    theme_name: str | None
    semester: str
    starts_on: date
    ends_on: date
    status: str
    created_at: datetime


class ProgressOut(BaseModel):
    """Progress summary for the passport countdown (FR-C3)."""

    total_weeks: int
    completed: int
    remaining: int
    is_prize_eligible: bool


class PassportOut(BaseModel):
    """Complete passport view: challenge + tasks with status + progress (UC-2)."""

    challenge: ChallengeOut
    tasks: list[TaskOut]
    progress: ProgressOut
    enrolled_at: datetime
