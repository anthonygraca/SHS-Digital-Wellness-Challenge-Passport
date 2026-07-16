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
    from datetime import datetime

    from app.repositories.dto import (
        AssessmentItemDTO,
        AssessmentResponseDTO,
        ChallengeDTO,
        CheckInAuditDTO,
        CheckInDTO,
        EnrollmentDTO,
        StudentDTO,
        TaskDTO,
        ThemeDTO,
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
    from app.schemas.theme import ThemeCreate, ThemeUpdate
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
    def get_student(self, campus_id: str, sso_subject: str) -> StudentDTO | None: ...
    def get_student_by_id(
        self, campus_id: str, student_id: StudentId
    ) -> StudentDTO | None: ...

    # --- Manual completion override + audit (FR-D6 / US-27) -----------------
    #
    # The load-bearing invariant, inherited from services/checkins.py: every mutator
    # writes its CheckIn change and its CheckInAudit row ATOMICALLY, so a completion
    # can never change without leaving a trace. SQL gets that from a single commit;
    # Dynamo uses TransactWriteItems across the two tables.
    def get_checkin(self, task_id: int, checkin_id: int) -> CheckInDTO | None: ...
    def list_task_checkins(self, task_id: int) -> list[tuple[CheckInDTO, StudentDTO]]: ...

    # The two reads behind the live event dashboard's count + recent feed (FR-D4 /
    # US-28). Split out from list_task_checkins on purpose: that one joins Students to
    # carry the subject, which the projected screen must never receive. These return a
    # number and ~6 identity-free rows, so the privacy property is structural rather
    # than a matter of the client remembering not to render a field it was handed.
    def count_task_checkins(self, task_id: int) -> int: ...
    def list_recent_task_checkins(self, task_id: int, limit: int) -> list[CheckInDTO]: ...
    def list_task_audits(
        self, task_id: int, student_id: StudentId | None = None
    ) -> list[CheckInAuditDTO]: ...
    def create_manual_checkin(
        self,
        *,
        campus_id: str,
        task: TaskDTO,
        student: StudentDTO,
        actor_subject: str,
        reason: str,
        ts: datetime | None = None,
    ) -> CheckInDTO:
        """Raises ValueError when the student already has a check-in for the task."""
        ...

    def correct_checkin(
        self,
        *,
        campus_id: str,
        checkin: CheckInDTO,
        student: StudentDTO,
        actor_subject: str,
        reason: str,
        method: str | None = None,
        ts: datetime | None = None,
    ) -> CheckInDTO: ...
    def remove_checkin(
        self,
        *,
        campus_id: str,
        checkin: CheckInDTO,
        student: StudentDTO,
        actor_subject: str,
        reason: str,
    ) -> None: ...

    # --- Assessments + engagement (FR-E4/E5, US-23) -------------------------
    #
    # Data access only. The scoring rules — which answer is correct, what a score may
    # be, which refusal wins — stay in services/assessments.py, which takes a Repository
    # and so runs unchanged on either backend. Duplicating those rules per backend is
    # exactly the drift this seam exists to prevent.
    def get_task_by_position(
        self, challenge_id: int, position: int
    ) -> TaskDTO | None: ...
    def get_item_in_challenge(
        self, challenge_id: int, item_id: int
    ) -> AssessmentItemDTO | None: ...
    def get_response(
        self, student_id: StudentId, item_id: int
    ) -> AssessmentResponseDTO | None: ...
    def get_responses_for_items(
        self, student_id: StudentId, item_ids: list[int]
    ) -> dict[int, AssessmentResponseDTO]: ...
    def create_response(
        self,
        *,
        student_id: StudentId,
        item: AssessmentItemDTO,
        challenge_id: int,
        response: str,
        score: float,
        scored_by: str,
        ai_feedback: str | None = None,
    ) -> AssessmentResponseDTO | None:
        """Returns None if the student already answered — one attempt per item. The
        conditional/constrained write, not the caller's pre-check, is the arbiter."""
        ...

    def list_item_responses(
        self, item_id: int
    ) -> list[tuple[AssessmentResponseDTO, StudentDTO]]: ...
    def get_item_response(
        self, item_id: int, response_id: int
    ) -> AssessmentResponseDTO | None: ...
    def override_response_score(
        self, response: AssessmentResponseDTO, score: float
    ) -> AssessmentResponseDTO: ...
    def record_content_view(
        self, *, student_id: StudentId, task: TaskDTO, content_ref: str
    ) -> None: ...
    def count_content_views(self, challenge_id: int) -> dict[str, int]:
        """content_ref -> number of views. Views, not viewers: re-reading a week is
        engagement, which is why nothing dedupes here (models/engagement.py)."""
        ...

    # --- Reporting (FR-F1..F5, read-only cohort-wide) -----------------------
    #
    # Bulk reads only; the aggregation — distinct-students vs raw-count, the outer
    # join that keeps a zero week/tag visible, the eligibility rule — stays in
    # services/reports.py so the counting is defined once. The challenge-scoped reads
    # are the Dynamo ByChallenge GSIs; on SQL they are the joins-through-Task.
    def count_enrollments(self, challenge_id: int) -> int: ...
    def list_challenge_tasks(self, challenge_id: int) -> list[TaskDTO]: ...
    def list_challenge_checkins(
        self, challenge_id: int, *, consistent: bool = False
    ) -> list[CheckInDTO]:
        """Every check-in for the challenge. ``consistent`` forces a strongly-consistent
        read: GSIs cannot be read consistently, so the prize export (US-26 scenario 2 —
        a just-recorded check-in must appear) reads the base table instead. The
        dashboards leave it False and tolerate the GSI's sub-second lag."""
        ...

    def count_guide_sessions(self, challenge_id: int) -> int: ...
    def list_challenge_items(self, challenge_id: int) -> list[AssessmentItemDTO]: ...
    def list_challenge_responses(
        self, challenge_id: int
    ) -> list[AssessmentResponseDTO]: ...
    def get_student_subjects(
        self, student_ids: list[StudentId]
    ) -> dict[StudentId, str]: ...

    # --- Themes (global re-skin presets, FR-B4 / US-13) ---------------------
    def list_themes(self) -> list[ThemeDTO]: ...
    def get_theme(self, theme_id: str) -> ThemeDTO | None: ...
    def create_theme(self, data: ThemeCreate) -> ThemeDTO: ...
    def update_theme(self, theme_id: str, data: ThemeUpdate) -> ThemeDTO | None: ...

    # --- Passport (derived reads + check-in writes) -------------------------
    def build_passport(
        self, campus_id: str, student_id: StudentId
    ) -> PassportView | None: ...
    def build_passport_for(
        self, challenge: ChallengeDTO, student_id: StudentId
    ) -> PassportView:
        """Assemble the passport for an already-resolved active challenge.

        ``challenge`` must have come from this same repository (``get_active_challenge``
        / ``get_challenge``). Exists so a caller that has already resolved the active
        challenge — /api/bootstrap, which needs it for the enrollment answer anyway —
        does not pay for a second lookup to also get the passport."""
        ...

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
