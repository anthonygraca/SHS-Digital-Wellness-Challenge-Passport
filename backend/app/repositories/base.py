"""The persistence seam.

`Repository` is the single interface the routers and the passport service depend on.
Two implementations back it:

- `SqlAlchemyRepository` — a thin adapter over the existing `app/services/*` functions
  and a SQLAlchemy `Session` (local dev + the pytest suite). Returns live ORM rows.
- `DynamoRepository` — a boto3 implementation over the multi-table DynamoDB model
  (AWS Lambda). Returns the DTOs in `app/repositories/dto.py`.

Both return objects with the same attribute names, so the response schemas
(`from_attributes=True`) and the passport service serialize either one identically.

`get_repo` is the FastAPI dependency; it picks the implementation from
`settings.persistence`. Tests override `get_repo` to inject a session-bound
`SqlAlchemyRepository` (see `tests/conftest.py`).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.repositories.dto import (
        AssessmentItemDTO,
        ChallengeDTO,
        EnrollmentDTO,
        StudentDTO,
        TaskDTO,
    )
    from app.schemas.challenge import (
        AssessmentItemUpdate,
        ChallengeCreate,
        ChallengeUpdate,
        MCQCreate,
        ReflectionCreate,
        TaskCreate,
        TaskReorder,
        TaskUpdate,
    )
    from app.services.passport import PassportView

# Student identity is an int PK on the SQL path and a "<campus>#<sso>" string on the
# Dynamo path; downstream code treats it as opaque (it is never exposed in responses).
StudentId = int | str


class Repository(Protocol):
    # --- Challenges ---------------------------------------------------------
    def create_challenge(self, campus_id: str, data: ChallengeCreate) -> ChallengeDTO: ...
    def list_challenges(self, campus_id: str) -> list[ChallengeDTO]: ...
    def get_challenge(self, campus_id: str, challenge_id: int) -> ChallengeDTO | None: ...
    def update_challenge(
        self, campus_id: str, challenge_id: int, data: ChallengeUpdate
    ) -> ChallengeDTO | None: ...
    def publish_challenge(
        self, campus_id: str, challenge_id: int
    ) -> ChallengeDTO | None: ...
    def get_active_challenge(self, campus_id: str) -> ChallengeDTO | None: ...

    # --- Tasks --------------------------------------------------------------
    def add_task(self, challenge_id: int, data: TaskCreate) -> TaskDTO: ...
    def get_task(self, challenge_id: int, task_id: int) -> TaskDTO | None: ...
    def update_task(
        self, challenge_id: int, task_id: int, data: TaskUpdate
    ) -> TaskDTO | None: ...
    def delete_task(self, challenge_id: int, task_id: int) -> None: ...
    def reorder_tasks(self, challenge_id: int, data: TaskReorder) -> list[TaskDTO]: ...

    # --- Assessment items ---------------------------------------------------
    def add_item(
        self, task_id: int, data: MCQCreate | ReflectionCreate
    ) -> AssessmentItemDTO: ...
    def list_items(self, task_id: int) -> list[AssessmentItemDTO]: ...
    def get_item(self, task_id: int, item_id: int) -> AssessmentItemDTO | None: ...
    def update_item(
        self, task_id: int, item_id: int, data: AssessmentItemUpdate
    ) -> AssessmentItemDTO | None: ...
    def delete_item(self, task_id: int, item_id: int) -> None: ...

    # --- Enrollment ---------------------------------------------------------
    def get_enrollment(
        self, student_id: StudentId, challenge_id: int
    ) -> EnrollmentDTO | None: ...
    def enroll(self, student_id: StudentId, challenge_id: int) -> EnrollmentDTO: ...

    # --- Students -----------------------------------------------------------
    def get_or_create_student(
        self, campus_id: str, sso_subject: str, affiliation: str
    ) -> StudentDTO: ...

    # --- Passport (derived reads + check-in writes) -------------------------
    def build_passport(
        self, campus_id: str, student_id: StudentId
    ) -> PassportView | None: ...
    def record_event_qr_checkin(
        self, campus_id: str, student_id: StudentId, token: str
    ) -> tuple[TaskDTO, PassportView]:
        """Record an event-QR check-in and return the completed task plus the refreshed
        passport. Returning both lets the caller avoid a second active-challenge lookup
        for the passport; raises InvalidEventToken / DuplicateCheckIn on failure."""
        ...


def get_repo() -> Iterator[Repository]:
    """FastAPI dependency yielding the configured repository.

    SQL: opens a Session for the request and closes it after. Dynamo: stateless
    boto3 client, nothing to close. Overridden in tests to bind a test session.
    """
    from app.config import get_settings

    settings = get_settings()

    if settings.persistence == "dynamo":
        from app.repositories.dynamo_repo import DynamoRepository

        yield DynamoRepository()
        return

    from app.db import SessionLocal
    from app.repositories.sqlalchemy_repo import SqlAlchemyRepository

    db = SessionLocal()
    try:
        yield SqlAlchemyRepository(db)
    finally:
        db.close()
