from __future__ import annotations

from pydantic import BaseModel


class ReportChallengeOut(BaseModel):
    """The challenge a report covers, trimmed to what the report header shows."""

    id: int
    name: str
    semester: str
    theme_id: str

    model_config = {"from_attributes": True}


class WeekCompletionOut(BaseModel):
    """One rung of the completion funnel: how many students finished this week.

    ``week_no`` is the task's 1-based position — the week number the passport
    and the report both show. A week with nobody finished still appears, with
    ``completed_count`` of 0.
    """

    task_id: int
    week_no: int
    title: str
    required: bool
    completed_count: int


class ParticipationReportOut(BaseModel):
    """Participation and the per-week completion funnel (FR-F1 / US-21).

    Counts only — no per-student rows — so the report stays aggregate and
    privacy-aware (FR-F6). The completion percentage is left to the client:
    it is a presentation choice, and the raw counts serve any renderer.
    """

    challenge: ReportChallengeOut
    total_enrollments: int
    weeks: list[WeekCompletionOut]
