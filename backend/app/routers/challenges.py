from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.auth.deps import require_admin
from app.repositories.base import Repository, get_repo
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
    """Edit challenge core attributes (name, semester, dates)."""
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
