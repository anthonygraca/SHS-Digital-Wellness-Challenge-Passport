"""Plain domain objects returned by the DynamoDB repository.

The SQLAlchemy repository returns live ORM rows; the DynamoDB repository returns
these dataclasses instead. Both are consumed the same way: the response schemas in
``app/schemas`` use ``from_attributes=True`` (attribute access), and the passport
service reads the same attribute names, so either shape serializes identically.

Field names and types deliberately mirror the ORM models in ``app/models`` so the
two backends are interchangeable behind the ``Repository`` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class AssessmentItemDTO:
    id: int
    task_id: int
    item_type: str
    prompt: str
    outcome_tag: str
    options: list | None
    answer_key: str | None
    rubric: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class TaskDTO:
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
    # Nested on get_challenge / task reads so ChallengeOut.tasks[*].assessment_items
    # serializes without a second round trip (mirrors the ORM relationship).
    assessment_items: list[AssessmentItemDTO] = field(default_factory=list)


@dataclass
class ChallengeDTO:
    id: int
    campus_id: str
    name: str
    semester: str
    start_date: date
    end_date: date
    status: str
    created_at: datetime
    updated_at: datetime
    # Not in ChallengeOut, but build_passport reads it for the passport theme.
    theme_id: str = ""
    tasks: list[TaskDTO] = field(default_factory=list)


@dataclass
class EnrollmentDTO:
    id: int | str
    student_id: int | str
    challenge_id: int
    enrolled_at: datetime


@dataclass
class StudentDTO:
    id: int | str
    campus_id: str
    sso_subject: str
    affiliation: str
    created_at: datetime


@dataclass
class CheckInDTO:
    id: int
    student_id: int | str
    task_id: int
    ts: datetime
    method: str
    verified_by: str | None


@dataclass
class CheckInAuditDTO:
    id: int
    campus_id: str
    student_id: int | str
    task_id: int
    checkin_id: int | None
    action: str
    actor_subject: str
    reason: str
    ts: datetime
    prior_state: dict | None
    new_state: dict | None


@dataclass
class ThemeDTO:
    id: str
    name: str
    palette: dict
    logo_url: str | None
    hero_url: str | None
    app_title: str
    tagline: str
    copy_tone: str
    created_at: datetime
    updated_at: datetime
