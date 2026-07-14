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
    dateStart: date
    dateEnd: date
    prize: str
    required: bool
    status: WeekStatus


class PassportOut(BaseModel):
    """The student's passport: challenge meta, derived counts, and week tiles.

    The SPA composes the "X of N complete, N remaining" countdown from the counts.
    """

    challengeName: str
    theme: str
    totalWeeks: int
    completedWeeks: int
    remainingWeeks: int
    weeks: list[WeekOut]


class CheckInRequest(BaseModel):
    """Body for a manual check-in: which week to complete."""

    weekNo: int
