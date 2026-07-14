from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

WeekStatus = Literal["locked", "available", "complete"]


class WeekOut(BaseModel):
    """One passport tile. Field names are camelCase for the SPA (no aliases)."""

    weekNo: int
    title: str
    caption: str
    activityType: str
    location: str
    # The admin builder (US-11) allows a task with no date window, so the SPA must
    # render the tile without one.
    dateStart: date | None = None
    dateEnd: date | None = None
    prize: str
    required: bool
    status: WeekStatus


class PassportOut(BaseModel):
    """The student's passport: challenge meta, derived counts, and week tiles.

    The SPA composes the "X of N complete, N remaining" countdown from the counts.
    ``prizeEligible`` is a derived query over required-task completion (US-7 /
    FR-C5), with the required counts supplied so the UI can show progress toward it.
    """

    challengeName: str
    theme: str
    totalWeeks: int
    completedWeeks: int
    remainingWeeks: int
    requiredTotal: int
    requiredCompleted: int
    prizeEligible: bool
    weeks: list[WeekOut]


class CheckInRequest(BaseModel):
    """Body for a manual check-in: which week to complete."""

    weekNo: int
