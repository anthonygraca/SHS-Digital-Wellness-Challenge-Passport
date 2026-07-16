from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_admin
from app.db import get_db
from app.models.student import Student
from app.repositories.base import Repository, get_repo
from app.schemas.challenge import (
    AssessmentItemCreate,
    AssessmentItemOut,
    AssessmentItemUpdate,
    AssessmentResponseOut,
    AssessmentScoreOverride,
    ChallengeCreate,
    ChallengeDuplicate,
    ChallengeOut,
    ChallengeSummary,
    ChallengeUpdate,
    CheckInAuditOut,
    CheckInCorrect,
    CheckInOut,
    CheckInRemove,
    ManualCheckInCreate,
    TaskCreate,
    TaskOut,
    TaskReorder,
    TaskUpdate,
)
from app.services import assessments as assessment_svc
from app.services import challenges as svc

router = APIRouter(prefix="/api/challenges", tags=["challenges"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_challenge_or_404(repo: Repository, campus_id: str, challenge_id: int):
    challenge = repo.get_challenge(campus_id, challenge_id)
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found"
        )
    return challenge


def _get_task_or_404(repo: Repository, challenge_id: int, task_id: int):
    task = repo.get_task(challenge_id, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return task


# ---------------------------------------------------------------------------
# Challenge endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ChallengeOut, status_code=status.HTTP_201_CREATED)
def create_challenge(
    body: ChallengeCreate,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Create a new draft challenge scoped to the caller's campus (FR-B1)."""
    return repo.create_challenge(claims["campus_id"], body)


@router.get("", response_model=list[ChallengeSummary])
def list_challenges(
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """List all challenges for the caller's campus."""
    return repo.list_challenges(claims["campus_id"])


@router.get("/{challenge_id}", response_model=ChallengeOut)
def get_challenge(
    challenge_id: int,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Fetch a single challenge (with its ordered tasks)."""
    return _get_challenge_or_404(repo, claims["campus_id"], challenge_id)


@router.patch("/{challenge_id}", response_model=ChallengeOut)
def update_challenge(
    challenge_id: int,
    body: ChallengeUpdate,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Edit challenge core attributes (name, semester, dates, theme)."""
    _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    return repo.update_challenge(claims["campus_id"], challenge_id, body)


@router.post("/{challenge_id}/publish", response_model=ChallengeOut)
def publish_challenge(
    challenge_id: int,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Transition a draft challenge to published status."""
    challenge = _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    if challenge.status == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Challenge is already published",
        )
    return repo.publish_challenge(claims["campus_id"], challenge_id)


@router.post(
    "/{challenge_id}/duplicate",
    response_model=ChallengeOut,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_challenge(
    challenge_id: int,
    body: ChallengeDuplicate | None = None,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
    db: Session = Depends(get_db),
):
    """Duplicate a challenge as a new editable draft (FR-B6).

    The original may be draft or published; the copy is always a draft. The body
    is optional — omitted, the copy takes a derived "<name> (Copy)" and the
    original's semester.
    """
    campus_id: str = claims["campus_id"]
    original = _get_challenge_or_404(repo, campus_id, challenge_id)
    try:
        return svc.duplicate_challenge(
            db, campus_id, original, body or ChallengeDuplicate()
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Task endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{challenge_id}/tasks",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
)
def add_task(
    challenge_id: int,
    body: TaskCreate,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Append a new task to a challenge (FR-B2)."""
    _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    return repo.add_task(challenge_id, body)


@router.patch("/{challenge_id}/tasks/{task_id}", response_model=TaskOut)
def update_task(
    challenge_id: int,
    task_id: int,
    body: TaskUpdate,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Edit a task's attributes."""
    _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    return repo.update_task(challenge_id, task_id, body)


@router.delete("/{challenge_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    challenge_id: int,
    task_id: int,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Remove a task and close the position gap."""
    _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    repo.delete_task(challenge_id, task_id)


@router.put("/{challenge_id}/tasks/order", response_model=list[TaskOut])
def reorder_tasks(
    challenge_id: int,
    body: TaskReorder,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Replace the task order with the provided ordered task ID list."""
    _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    try:
        return repo.reorder_tasks(challenge_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Assessment item endpoints (FR-B3)
# ---------------------------------------------------------------------------


def _get_item_or_404(repo: Repository, task_id: int, item_id: int):
    item = repo.get_item(task_id, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment item not found"
        )
    return item


@router.post(
    "/{challenge_id}/tasks/{task_id}/items",
    response_model=AssessmentItemOut,
    status_code=status.HTTP_201_CREATED,
)
def add_assessment_item(
    challenge_id: int,
    task_id: int,
    body: Annotated[AssessmentItemCreate, Body()],
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Attach an MCQ or reflection item to a task tagged to a learning outcome (FR-B3)."""
    _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    return repo.add_item(task_id, body)


@router.get(
    "/{challenge_id}/tasks/{task_id}/items",
    response_model=list[AssessmentItemOut],
)
def list_assessment_items(
    challenge_id: int,
    task_id: int,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """List all assessment items attached to a task."""
    _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    return repo.list_items(task_id)


@router.patch(
    "/{challenge_id}/tasks/{task_id}/items/{item_id}",
    response_model=AssessmentItemOut,
)
def update_assessment_item(
    challenge_id: int,
    task_id: int,
    item_id: int,
    body: AssessmentItemUpdate,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Edit an assessment item's attributes."""
    _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    _get_item_or_404(repo, task_id, item_id)
    return repo.update_item(task_id, item_id, body)


@router.delete(
    "/{challenge_id}/tasks/{task_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_assessment_item(
    challenge_id: int,
    task_id: int,
    item_id: int,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Remove an assessment item from a task."""
    _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    _get_item_or_404(repo, task_id, item_id)
    repo.delete_item(task_id, item_id)


# ---------------------------------------------------------------------------
# Manual completion override + audit (FR-D6)
# ---------------------------------------------------------------------------


def _get_student_or_404(repo: Repository, campus_id: str, sso_subject: str):
    """Resolve a student by SSO subject within the caller's campus.

    Student rows are only ever minted by /auth/acs, so an unknown subject means
    the student has not signed in here yet. Deliberately NOT get_or_create: that
    would let an admin mint arbitrary unverified subjects and quietly pollute
    enrollment and eligibility data.
    """
    student = repo.get_student(campus_id, sso_subject)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "That student hasn't signed in at your campus yet — "
                "have them sign in once, then retry."
            ),
        )
    return student


def _get_student_or_404_by_id(repo: Repository, campus_id: str, student_id):
    """Load the student a check-in points at, for its subject and audit snapshot.

    The campus filter is belt-and-braces: the check-in was already reached via a
    campus-scoped challenge, so a mismatch here would mean cross-campus data.
    """
    student = repo.get_student_by_id(campus_id, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )
    return student


def _get_checkin_or_404(repo: Repository, task_id: int, checkin_id: int):
    checkin = repo.get_checkin(task_id, checkin_id)
    if checkin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found"
        )
    return checkin


def _checkin_out(checkin, student) -> CheckInOut:
    """Assemble the response — student_subject lives on the Student row."""
    return CheckInOut(
        id=checkin.id,
        student_id=checkin.student_id,
        student_subject=student.sso_subject,
        task_id=checkin.task_id,
        ts=checkin.ts,
        method=checkin.method,
        verified_by=checkin.verified_by,
    )


@router.post(
    "/{challenge_id}/tasks/{task_id}/checkins",
    response_model=CheckInOut,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_checkin(
    challenge_id: int,
    task_id: int,
    body: ManualCheckInCreate,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Manually mark a student complete, writing an audit row (FR-D6 / US-27)."""
    campus_id: str = claims["campus_id"]
    _get_challenge_or_404(repo, campus_id, challenge_id)
    task = _get_task_or_404(repo, challenge_id, task_id)
    student = _get_student_or_404(repo, campus_id, body.student_subject)

    try:
        checkin = repo.create_manual_checkin(
            campus_id=campus_id,
            task=task,
            student=student,
            actor_subject=claims["sub"],
            reason=body.reason,
            ts=body.ts,
        )
    except ValueError as exc:
        # An existing completion is an override, not a create — different audit
        # action, so the caller must say which they meant.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return _checkin_out(checkin, student)


@router.get(
    "/{challenge_id}/tasks/{task_id}/checkins",
    response_model=list[CheckInOut],
)
def list_checkins(
    challenge_id: int,
    task_id: int,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """List every check-in recorded for a task."""
    _get_challenge_or_404(repo, claims["campus_id"], challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    return [
        _checkin_out(checkin, student)
        for checkin, student in repo.list_task_checkins(task_id)
    ]


@router.patch(
    "/{challenge_id}/tasks/{task_id}/checkins/{checkin_id}",
    response_model=CheckInOut,
)
def correct_checkin(
    challenge_id: int,
    task_id: int,
    checkin_id: int,
    body: CheckInCorrect,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Correct an existing check-in, preserving the prior state for audit."""
    campus_id: str = claims["campus_id"]
    _get_challenge_or_404(repo, campus_id, challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    checkin = _get_checkin_or_404(repo, task_id, checkin_id)
    student = _get_student_or_404_by_id(repo, campus_id, checkin.student_id)

    updated = repo.correct_checkin(
        campus_id=campus_id,
        checkin=checkin,
        student=student,
        actor_subject=claims["sub"],
        reason=body.reason,
        method=body.method,
        ts=body.ts,
    )
    return _checkin_out(updated, student)


@router.delete(
    "/{challenge_id}/tasks/{task_id}/checkins/{checkin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_checkin(
    challenge_id: int,
    task_id: int,
    checkin_id: int,
    body: CheckInRemove,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Remove an erroneous check-in. The audit snapshot preserves it (FR-D6)."""
    campus_id: str = claims["campus_id"]
    _get_challenge_or_404(repo, campus_id, challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    checkin = _get_checkin_or_404(repo, task_id, checkin_id)
    student = _get_student_or_404_by_id(repo, campus_id, checkin.student_id)

    repo.remove_checkin(
        campus_id=campus_id,
        checkin=checkin,
        student=student,
        actor_subject=claims["sub"],
        reason=body.reason,
    )


@router.get(
    "/{challenge_id}/tasks/{task_id}/audits",
    response_model=list[CheckInAuditOut],
)
def list_checkin_audits(
    challenge_id: int,
    task_id: int,
    student_subject: str | None = None,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Read the append-only audit ledger for a task, newest first (FR-D6)."""
    campus_id: str = claims["campus_id"]
    _get_challenge_or_404(repo, campus_id, challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)

    student_id = None
    if student_subject is not None:
        student_id = _get_student_or_404(repo, campus_id, student_subject).id
    return repo.list_task_audits(task_id, student_id)


# ---------------------------------------------------------------------------
# Reflection scoring override (FR-E5)
#
# Nested under the challenge/task/item path rather than hung off /api/assessments so
# that _get_challenge_or_404 -> _get_task_or_404 -> _get_item_or_404 supplies the campus
# isolation for free. The student-side helper in services/assessments.py cannot serve an
# admin: it is scoped to the *published* challenge, and an admin must be able to read and
# fix scores on a draft.
#
# Deliberately no audit ledger, unlike the FR-D6 check-in override above. FR-D6 demands
# one; FR-E5 asks only that scored_by become "human", and that field on the row is the
# record. CheckInAudit is check-in-shaped and not reusable here, and a table nothing
# requires is the same debt as a column nothing can write.
# ---------------------------------------------------------------------------


def _get_response_or_404(db: Session, item_id: int, response_id: int):
    response = assessment_svc.get_item_response(db, item_id, response_id)
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Response not found"
        )
    return response


def _response_out(response, student: Student) -> AssessmentResponseOut:
    """Assemble the response — student_subject lives on the Student row."""
    return AssessmentResponseOut(
        id=response.id,
        student_id=response.student_id,
        student_subject=student.sso_subject,
        response=response.response,
        score=response.score,
        scored_by=response.scored_by,
        ai_feedback=response.ai_feedback,
        ts=response.ts,
    )


@router.get(
    "/{challenge_id}/tasks/{task_id}/items/{item_id}/responses",
    response_model=list[AssessmentResponseOut],
)
def list_item_responses(
    challenge_id: int,
    task_id: int,
    item_id: int,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
    db: Session = Depends(get_db),
):
    """Every student response to one assessment item, newest first (FR-E5).

    The reading surface for the score override: an admin cannot sensibly adjust a score
    without seeing the reflection and the feedback it was given.
    """
    campus_id: str = claims["campus_id"]
    _get_challenge_or_404(repo, campus_id, challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    _get_item_or_404(repo, task_id, item_id)

    return [
        _response_out(response, student)
        for response, student in assessment_svc.list_item_responses(db, item_id)
    ]


@router.patch(
    "/{challenge_id}/tasks/{task_id}/items/{item_id}/responses/{response_id}",
    response_model=AssessmentResponseOut,
)
def override_response_score(
    challenge_id: int,
    task_id: int,
    item_id: int,
    response_id: int,
    body: AssessmentScoreOverride,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
    db: Session = Depends(get_db),
):
    """Adjust a score by hand, marking it scored_by "human" (US-19 / FR-E5).

    An UPDATE of the existing row, not a new one: the one-attempt constraint means there
    is exactly one response per student per item, and the override is a correction to it
    rather than a second opinion beside it.

    Item-type-agnostic on purpose. FR-E5 motivates it for reflections, but nothing about
    the operation is reflection-specific, and an admin repairing scores after a bad MCQ
    answer key is a real need this already answers. Refusing that would need a reason the
    requirement does not supply.
    """
    campus_id: str = claims["campus_id"]
    _get_challenge_or_404(repo, campus_id, challenge_id)
    _get_task_or_404(repo, challenge_id, task_id)
    _get_item_or_404(repo, task_id, item_id)
    response = _get_response_or_404(db, item_id, response_id)
    student = _get_student_or_404_by_id(repo, campus_id, response.student_id)

    updated = assessment_svc.override_response_score(db, response, body.score)
    return _response_out(updated, student)
