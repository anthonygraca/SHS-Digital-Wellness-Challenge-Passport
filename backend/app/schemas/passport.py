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


class ThemeConfigOut(BaseModel):
    """The resolved re-skin config for the student app (FR-B4).

    Carries the palette, assets and copy as data so a semester re-skin needs no
    code deployment (NFR-6). ``palette`` maps a CSS custom-property suffix to its
    value — the app applies each as ``--wp-<key>``.
    """

    id: str
    palette: dict[str, str]
    logoUrl: str | None = None
    heroUrl: str | None = None
    appTitle: str
    tagline: str
    copyTone: str


class PassportOut(BaseModel):
    """The student's passport: challenge meta, derived counts, and week tiles.

    The SPA composes the "X of N complete, N remaining" countdown from the counts.
    ``prizeEligible`` is a derived query over required-task completion (US-7 /
    FR-C5), with the required counts supplied so the UI can show progress toward it.
    """

    challengeName: str
    # The theme's id, kept for the app's static per-theme token blocks; null
    # ``themeConfig`` means the default theme (unset or unknown ``theme``).
    theme: str
    themeConfig: ThemeConfigOut | None = None
    totalWeeks: int
    completedWeeks: int
    remainingWeeks: int
    requiredTotal: int
    requiredCompleted: int
    prizeEligible: bool
    weeks: list[WeekOut]


class ScanCheckInRequest(BaseModel):
    """Body for a QR check-in: the signed token decoded from the scanned event QR."""

    token: str


class CheckInResult(BaseModel):
    """Result of a successful QR check-in: the refreshed passport plus the tip to show.

    ``weekNo``/``title`` identify the week that just flipped to complete so the SPA can
    celebrate it; ``tip`` is the personalized message shown after check-in (FR-E1).
    """

    passport: PassportOut
    tip: str
    weekNo: int
    title: str
