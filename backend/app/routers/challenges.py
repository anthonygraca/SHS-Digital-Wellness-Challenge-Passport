from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_admin
from app.db import get_db
from app.schemas.challenge import (
    AssessmentItemCreate,
    AssessmentItemOut,
    AssessmentItemUpdate,
    ChallengeCreate,
    ChallengeOut,
    ChallengeSummary,
    ChallengeUpdate,
    TaskCreate,
    TaskOut,
    TaskReorder,
    TaskUpdate,
)
from app.services import challenges as svc

router = APIRouter(prefix="/api/challenges", tags=["challenges"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_challenge_or_404(db: Session, campus_id: str, challenge_id: int):
    challenge = svc.get_challenge(db, campus_id, challenge_id)
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found"
        )
    return challenge


def _get_task_or_404(db: Session, challenge_id: int, task_id: int):
    task = svc.get_task(db, challenge_id, task_id)
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
    db: Session = Depends(get_db),
):
    """Create a new draft challenge scoped to the caller's campus (FR-B1)."""
    campus_id: str = claims["campus_id"]
    challenge = svc.create_challenge(db, campus_id, body)
    return challenge


@router.get("", response_model=list[ChallengeSummary])
def list_challenges(
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all challenges for the caller's campus."""
    return svc.list_challenges(db, claims["campus_id"])


@router.get("/{challenge_id}", response_model=ChallengeOut)
def get_challenge(
    challenge_id: int,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Fetch a single challenge (with its ordered tasks)."""
    return _get_challenge_or_404(db, claims["campus_id"], challenge_id)


@router.patch("/{challenge_id}", response_model=ChallengeOut)
def update_challenge(
    challenge_id: int,
    body: ChallengeUpdate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Edit challenge core attributes (name, semester, dates)."""
    challenge = _get_challenge_or_404(db, claims["campus_id"], challenge_id)
    return svc.update_challenge(db, challenge, body)


@router.post("/{challenge_id}/publish", response_model=ChallengeOut)
def publish_challenge(
    challenge_id: int,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Transition a draft challenge to published status."""
    challenge = _get_challenge_or_404(db, claims["campus_id"], challenge_id)
    if challenge.status == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Challenge is already published",
        )
    return svc.publish_challenge(db, challenge)


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
    db: Session = Depends(get_db),
):
    """Append a new task to a challenge (FR-B2)."""
    challenge = _get_challenge_or_404(db, claims["campus_id"], challenge_id)
    return svc.add_task(db, challenge, body)


@router.patch("/{challenge_id}/tasks/{task_id}", response_model=TaskOut)
def update_task(
    challenge_id: int,
    task_id: int,
    body: TaskUpdate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Edit a task's attributes."""
    _get_challenge_or_404(db, claims["campus_id"], challenge_id)
    task = _get_task_or_404(db, challenge_id, task_id)
    return svc.update_task(db, task, body)


@router.delete("/{challenge_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    challenge_id: int,
    task_id: int,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove a task and close the position gap."""
    _get_challenge_or_404(db, claims["campus_id"], challenge_id)
    task = _get_task_or_404(db, challenge_id, task_id)
    svc.delete_task(db, task)


@router.put("/{challenge_id}/tasks/order", response_model=list[TaskOut])
def reorder_tasks(
    challenge_id: int,
    body: TaskReorder,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Replace the task order with the provided ordered task ID list."""
    challenge = _get_challenge_or_404(db, claims["campus_id"], challenge_id)
    try:
        return svc.reorder_tasks(db, challenge, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Assessment item endpoints (FR-B3)
# ---------------------------------------------------------------------------


def _get_item_or_404(db: Session, task_id: int, item_id: int):
    item = svc.get_assessment_item(db, task_id, item_id)
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
    db: Session = Depends(get_db),
):
    """Attach an MCQ or reflection item to a task, tagged to a learning outcome (FR-B3)."""
    _get_challenge_or_404(db, claims["campus_id"], challenge_id)
    task = _get_task_or_404(db, challenge_id, task_id)
    return svc.add_assessment_item(db, task, body)


@router.get(
    "/{challenge_id}/tasks/{task_id}/items",
    response_model=list[AssessmentItemOut],
)
def list_assessment_items(
    challenge_id: int,
    task_id: int,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all assessment items attached to a task."""
    _get_challenge_or_404(db, claims["campus_id"], challenge_id)
    _get_task_or_404(db, challenge_id, task_id)
    return svc.list_assessment_items(db, task_id)


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
    db: Session = Depends(get_db),
):
    """Edit an assessment item's attributes."""
    _get_challenge_or_404(db, claims["campus_id"], challenge_id)
    _get_task_or_404(db, challenge_id, task_id)
    item = _get_item_or_404(db, task_id, item_id)
    return svc.update_assessment_item(db, item, body)


@router.delete(
    "/{challenge_id}/tasks/{task_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_assessment_item(
    challenge_id: int,
    task_id: int,
    item_id: int,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove an assessment item from a task."""
    _get_challenge_or_404(db, claims["campus_id"], challenge_id)
    _get_task_or_404(db, challenge_id, task_id)
    item = _get_item_or_404(db, task_id, item_id)
    svc.delete_assessment_item(db, item)
