"""SQLAlchemy-backed repository — the local-dev + test implementation.

Deliberately a thin adapter: every method delegates to the existing
`app/services/*` functions with this repository's `Session`, so the SQL code path
is byte-for-byte the behaviour the pytest suite already exercises. It returns live
ORM rows (structurally interchangeable with the DTOs the Dynamo repo returns).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.challenge import (
    AssessmentItem,
    AssessmentResponse,
    Challenge,
    CheckIn,
    Enrollment,
    Task,
)
from app.models.engagement import ContentView, GuideSession
from app.models.student import Student
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
from app.services import checkins as checkin_svc
from app.services import enrollment as enrollment_svc
from app.services import passport as passport_svc
from app.services import students as student_svc
from app.services import themes as theme_svc


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

    def get_student(self, campus_id: str, sso_subject: str):
        return student_svc.get_student(self.db, campus_id, sso_subject)

    def get_student_by_id(self, campus_id: str, student_id):
        student = self.db.get(Student, student_id)
        if student is None or student.campus_id != campus_id:
            return None
        return student

    # --- Manual completion override + audit (FR-D6) -------------------------
    def get_checkin(self, task_id: int, checkin_id: int):
        return checkin_svc.get_checkin(self.db, task_id, checkin_id)

    def list_task_checkins(self, task_id: int):
        return checkin_svc.list_task_checkins(self.db, task_id)

    def count_task_checkins(self, task_id: int) -> int:
        return checkin_svc.count_task_checkins(self.db, task_id)

    def list_recent_task_checkins(self, task_id: int, limit: int):
        return checkin_svc.list_recent_task_checkins(self.db, task_id, limit)

    def list_task_audits(self, task_id: int, student_id=None):
        return checkin_svc.list_task_audits(self.db, task_id, student_id)

    def create_manual_checkin(
        self, *, campus_id, task, student, actor_subject, reason, ts=None
    ):
        return checkin_svc.create_manual_checkin(
            self.db,
            campus_id=campus_id,
            task=task,
            student=student,
            actor_subject=actor_subject,
            reason=reason,
            ts=ts,
        )

    def correct_checkin(
        self, *, campus_id, checkin, student, actor_subject, reason, method=None, ts=None
    ):
        return checkin_svc.correct_checkin(
            self.db,
            campus_id=campus_id,
            checkin=checkin,
            student=student,
            actor_subject=actor_subject,
            reason=reason,
            method=method,
            ts=ts,
        )

    def remove_checkin(self, *, campus_id, checkin, student, actor_subject, reason):
        checkin_svc.remove_checkin(
            self.db,
            campus_id=campus_id,
            checkin=checkin,
            student=student,
            actor_subject=actor_subject,
            reason=reason,
        )

    # --- Assessments + engagement (FR-E4/E5, US-23) -------------------------
    def get_task_by_position(self, challenge_id: int, position: int):
        return (
            self.db.execute(
                select(Task)
                .where(Task.challenge_id == challenge_id, Task.position == position)
                .order_by(Task.id)
            )
            .scalars()
            .first()
        )

    def get_item_in_challenge(self, challenge_id: int, item_id: int):
        return self.db.execute(
            select(AssessmentItem)
            .join(Task, Task.id == AssessmentItem.task_id)
            .where(AssessmentItem.id == item_id, Task.challenge_id == challenge_id)
        ).scalar_one_or_none()

    def get_response(self, student_id, item_id: int):
        return self.db.execute(
            select(AssessmentResponse).where(
                AssessmentResponse.student_id == student_id,
                AssessmentResponse.assessment_item_id == item_id,
            )
        ).scalar_one_or_none()

    def get_responses_for_items(self, student_id, item_ids: list[int]):
        if not item_ids:
            return {}
        rows = (
            self.db.execute(
                select(AssessmentResponse).where(
                    AssessmentResponse.student_id == student_id,
                    AssessmentResponse.assessment_item_id.in_(item_ids),
                )
            )
            .scalars()
            .all()
        )
        return {r.assessment_item_id: r for r in rows}

    def create_response(
        self,
        *,
        student_id,
        item,
        challenge_id: int,
        response: str,
        score: float,
        scored_by: str,
        ai_feedback: str | None = None,
    ):
        # challenge_id is unused here — it exists for the Dynamo path's ByChallenge
        # index; on SQL the response reaches its challenge through the item's task.
        row = AssessmentResponse(
            student_id=student_id,
            assessment_item_id=item.id,
            response=response,
            score=score,
            scored_by=scored_by,
            ai_feedback=ai_feedback,
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            # uq_response_student_item — the student already answered.
            self.db.rollback()
            return None
        self.db.refresh(row)
        return row

    def list_item_responses(self, item_id: int):
        rows = self.db.execute(
            select(AssessmentResponse, Student)
            .join(Student, Student.id == AssessmentResponse.student_id)
            .where(AssessmentResponse.assessment_item_id == item_id)
            .order_by(AssessmentResponse.ts.desc())
        ).all()
        return [(response, student) for response, student in rows]

    def get_item_response(self, item_id: int, response_id: int):
        return self.db.execute(
            select(AssessmentResponse).where(
                AssessmentResponse.id == response_id,
                AssessmentResponse.assessment_item_id == item_id,
            )
        ).scalar_one_or_none()

    def override_response_score(self, response, score: float):
        response.score = score
        response.scored_by = "human"
        self.db.commit()
        self.db.refresh(response)
        return response

    def record_content_view(self, *, student_id, task, content_ref: str) -> None:
        self.db.add(
            ContentView(student_id=student_id, task_id=task.id, content_ref=content_ref)
        )
        self.db.commit()

    def count_content_views(self, challenge_id: int) -> dict[str, int]:
        # ContentView reaches its challenge through the task, exactly as CheckIn does —
        # that join is what keeps another campus's rows out of the count.
        rows = self.db.execute(
            select(ContentView.content_ref, func.count())
            .join(Task, Task.id == ContentView.task_id)
            .where(Task.challenge_id == challenge_id)
            .group_by(ContentView.content_ref)
        ).all()
        return {ref: count for ref, count in rows}

    # --- Reporting (FR-F1..F5) ----------------------------------------------
    # Bulk challenge-scoped reads; the aggregation lives in services/reports.py.
    # ``consistent`` is a no-op here (SQLite reads are already consistent) — it is
    # only meaningful on the Dynamo GSI path.
    def count_enrollments(self, challenge_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Enrollment)
                .where(Enrollment.challenge_id == challenge_id)
            )
            or 0
        )

    def list_challenge_tasks(self, challenge_id: int):
        return list(
            self.db.execute(
                select(Task)
                .where(Task.challenge_id == challenge_id)
                .order_by(Task.position)
            ).scalars()
        )

    def list_challenge_checkins(self, challenge_id: int, *, consistent: bool = False):
        return list(
            self.db.execute(
                select(CheckIn)
                .join(Task, Task.id == CheckIn.task_id)
                .where(Task.challenge_id == challenge_id)
            ).scalars()
        )

    def count_guide_sessions(self, challenge_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(GuideSession)
                .where(GuideSession.challenge_id == challenge_id)
            )
            or 0
        )

    def list_challenge_items(self, challenge_id: int):
        return list(
            self.db.execute(
                select(AssessmentItem)
                .join(Task, Task.id == AssessmentItem.task_id)
                .where(Task.challenge_id == challenge_id)
            ).scalars()
        )

    def list_challenge_responses(self, challenge_id: int):
        return list(
            self.db.execute(
                select(AssessmentResponse)
                .join(
                    AssessmentItem,
                    AssessmentItem.id == AssessmentResponse.assessment_item_id,
                )
                .join(Task, Task.id == AssessmentItem.task_id)
                .where(Task.challenge_id == challenge_id)
            ).scalars()
        )

    def get_student_subjects(self, student_ids):
        if not student_ids:
            return {}
        rows = self.db.execute(
            select(Student.id, Student.sso_subject).where(Student.id.in_(student_ids))
        ).all()
        return {sid: subject for sid, subject in rows}

    # --- Themes -------------------------------------------------------------
    def list_themes(self):
        return theme_svc.list_themes(self.db)

    def get_theme(self, theme_id: str):
        return theme_svc.get_theme(self.db, theme_id)

    def create_theme(self, data):
        return theme_svc.create_theme(self.db, data)

    def update_theme(self, theme_id: str, data):
        theme = theme_svc.get_theme(self.db, theme_id)
        if theme is None:
            return None
        return theme_svc.update_theme(self.db, theme, data)

    # --- Passport -----------------------------------------------------------
    def build_passport(self, campus_id: str, student_id):
        return passport_svc.build_passport(
            self.db, campus_id=campus_id, student_id=student_id
        )

    def build_passport_for(self, challenge, student_id):
        return passport_svc.build_passport_for(
            self.db, challenge=challenge, student_id=student_id
        )

    def record_event_qr_checkin(self, campus_id: str, student_id, token: str):
        # Returns (task, refreshed passport) to match the Dynamo path, which resolves
        # the active challenge once and reuses it. On SQL both reads are cheap session
        # queries, so this just keeps the interface uniform.
        task = passport_svc.record_event_qr_checkin(
            self.db, campus_id=campus_id, student_id=student_id, token=token
        )
        view = passport_svc.build_passport(
            self.db, campus_id=campus_id, student_id=student_id
        )
        return task, view
