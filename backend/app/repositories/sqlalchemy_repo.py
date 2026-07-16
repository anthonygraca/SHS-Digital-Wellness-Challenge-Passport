"""SQLAlchemy-backed repository — the local-dev + test implementation.

Deliberately a thin adapter: every method delegates to the existing
`app/services/*` functions with this repository's `Session`, so the SQL code path
is byte-for-byte the behaviour the pytest suite already exercises. It returns live
ORM rows (structurally interchangeable with the DTOs the Dynamo repo returns).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.challenge import Challenge, Task
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
from app.services import challenges as challenge_svc
from app.services import enrollment as enrollment_svc
from app.services import passport as passport_svc
from app.services import students as student_svc


class SqlAlchemyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Challenges ---------------------------------------------------------
    def create_challenge(self, campus_id: str, data: ChallengeCreate):
        return challenge_svc.create_challenge(self.db, campus_id, data)

    def list_challenges(self, campus_id: str):
        return challenge_svc.list_challenges(self.db, campus_id)

    def get_challenge(self, campus_id: str, challenge_id: int):
        return challenge_svc.get_challenge(self.db, campus_id, challenge_id)

    def update_challenge(self, campus_id: str, challenge_id: int, data: ChallengeUpdate):
        challenge = challenge_svc.get_challenge(self.db, campus_id, challenge_id)
        if challenge is None:
            return None
        return challenge_svc.update_challenge(self.db, challenge, data)

    def publish_challenge(self, campus_id: str, challenge_id: int):
        challenge = challenge_svc.get_challenge(self.db, campus_id, challenge_id)
        if challenge is None:
            return None
        return challenge_svc.publish_challenge(self.db, challenge)

    def get_active_challenge(self, campus_id: str):
        return challenge_svc.get_active_challenge_for_campus(self.db, campus_id)

    # --- Tasks --------------------------------------------------------------
    def add_task(self, challenge_id: int, data: TaskCreate):
        challenge = self.db.get(Challenge, challenge_id)
        return challenge_svc.add_task(self.db, challenge, data)

    def get_task(self, challenge_id: int, task_id: int):
        return challenge_svc.get_task(self.db, challenge_id, task_id)

    def update_task(self, challenge_id: int, task_id: int, data: TaskUpdate):
        task = challenge_svc.get_task(self.db, challenge_id, task_id)
        if task is None:
            return None
        return challenge_svc.update_task(self.db, task, data)

    def delete_task(self, challenge_id: int, task_id: int) -> None:
        task = challenge_svc.get_task(self.db, challenge_id, task_id)
        if task is not None:
            challenge_svc.delete_task(self.db, task)

    def reorder_tasks(self, challenge_id: int, data: TaskReorder):
        challenge = self.db.get(Challenge, challenge_id)
        return challenge_svc.reorder_tasks(self.db, challenge, data)

    # --- Assessment items ---------------------------------------------------
    def add_item(self, task_id: int, data: MCQCreate | ReflectionCreate):
        task = self.db.get(Task, task_id)
        return challenge_svc.add_assessment_item(self.db, task, data)

    def list_items(self, task_id: int):
        return challenge_svc.list_assessment_items(self.db, task_id)

    def get_item(self, task_id: int, item_id: int):
        return challenge_svc.get_assessment_item(self.db, task_id, item_id)

    def update_item(self, task_id: int, item_id: int, data: AssessmentItemUpdate):
        item = challenge_svc.get_assessment_item(self.db, task_id, item_id)
        if item is None:
            return None
        return challenge_svc.update_assessment_item(self.db, item, data)

    def delete_item(self, task_id: int, item_id: int) -> None:
        item = challenge_svc.get_assessment_item(self.db, task_id, item_id)
        if item is not None:
            challenge_svc.delete_assessment_item(self.db, item)

    # --- Enrollment ---------------------------------------------------------
    def get_enrollment(self, student_id, challenge_id: int):
        return enrollment_svc.get_enrollment(self.db, student_id, challenge_id)

    def enroll(self, student_id, challenge_id: int):
        enrollment, _created = enrollment_svc.get_or_create_enrollment(
            self.db, student_id, challenge_id
        )
        return enrollment

    # --- Students -----------------------------------------------------------
    def get_or_create_student(self, campus_id: str, sso_subject: str, affiliation: str):
        student, _created = student_svc.get_or_create_student(
            self.db, campus_id, sso_subject, affiliation
        )
        return student

    # --- Passport -----------------------------------------------------------
    def build_passport(self, campus_id: str, student_id):
        return passport_svc.build_passport(
            self.db, campus_id=campus_id, student_id=student_id
        )

    def record_event_qr_checkin(self, campus_id: str, student_id, token: str):
        return passport_svc.record_event_qr_checkin(
            self.db, campus_id=campus_id, student_id=student_id, token=token
        )
