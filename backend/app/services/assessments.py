from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.challenge import AssessmentItem, AssessmentResponse, Task
from app.services.challenges import get_active_challenge_for_campus

# An MCQ is all-or-nothing: it has exactly one keyed option. The float range is
# shared with US-19's rubric scoring, which lands between these two.
CORRECT_SCORE = 1.0
INCORRECT_SCORE = 0.0

MCQ_ITEM_TYPE = "mcq"


class ItemNotFound(Exception):
    """No such item in this campus's active published challenge."""


class NotAnMCQ(Exception):
    """The item exists but is a reflection — US-19 scores those, not this path."""


class UnknownOption(Exception):
    """The submitted answer is not one of the item's options."""


class DuplicateResponse(Exception):
    """The student already answered this item; an MCQ is one attempt."""


@dataclass
class ScoredResponse:
    """The outcome of auto-scoring one MCQ submission."""

    item_id: int
    outcome_tag: str
    response: str
    score: float
    correct: bool
    correct_option: str
    scored_by: str


@dataclass
class StoredResponseView:
    """A student's own already-stored answer to an item."""

    response: str
    score: float
    correct: bool
    scored_by: str
    ts: datetime


@dataclass
class KnowledgeCheckItemView:
    """An MCQ as the student may see it — no answer key, by construction."""

    id: int
    week_no: int
    prompt: str
    outcome_tag: str
    options: list[str]
    your_response: StoredResponseView | None


def _stored_view(response: AssessmentResponse | None) -> StoredResponseView | None:
    if response is None:
        return None
    return StoredResponseView(
        response=response.response,
        score=response.score,
        correct=response.score == CORRECT_SCORE,
        scored_by=response.scored_by,
        ts=response.ts,
    )


def list_week_items(
    db: Session, *, campus_id: str, student_id: int, week_no: int
) -> list[KnowledgeCheckItemView] | None:
    """The MCQs on one week of the campus's active challenge, with the student's answers.

    Returns ``None`` when the campus has no published challenge or has no such week —
    the caller 404s. An empty list means the week exists but carries no knowledge check,
    which is the common case and not an error.

    Reflections are filtered out: US-19 owns that surface, and this branch has no way
    to render or score one.
    """
    challenge = get_active_challenge_for_campus(db, campus_id)
    if challenge is None:
        return None

    task = db.execute(
        select(Task).where(Task.challenge_id == challenge.id, Task.position == week_no)
    ).scalar_one_or_none()
    if task is None:
        return None

    items = (
        db.execute(
            select(AssessmentItem)
            .where(
                AssessmentItem.task_id == task.id,
                AssessmentItem.item_type == MCQ_ITEM_TYPE,
            )
            .order_by(AssessmentItem.id)
        )
        .scalars()
        .all()
    )
    if not items:
        return []

    responses = {
        r.assessment_item_id: r
        for r in db.execute(
            select(AssessmentResponse).where(
                AssessmentResponse.student_id == student_id,
                AssessmentResponse.assessment_item_id.in_([i.id for i in items]),
            )
        )
        .scalars()
        .all()
    }

    return [
        KnowledgeCheckItemView(
            id=item.id,
            week_no=task.position,
            prompt=item.prompt,
            outcome_tag=item.outcome_tag,
            options=list(item.options or []),
            your_response=_stored_view(responses.get(item.id)),
        )
        for item in items
    ]


def _item_in_active_challenge(
    db: Session, *, campus_id: str, item_id: int
) -> AssessmentItem | None:
    """Load an item only if it sits in the campus's active published challenge.

    The join through Task -> Challenge *is* the campus isolation, and it is why the
    caller can 404 rather than 403: an item id belonging to another campus, or to a
    draft challenge, is indistinguishable from one that does not exist — which is the
    intended answer, since existence is itself not the student's to learn.
    """
    challenge = get_active_challenge_for_campus(db, campus_id)
    if challenge is None:
        return None
    return db.execute(
        select(AssessmentItem)
        .join(Task, Task.id == AssessmentItem.task_id)
        .where(AssessmentItem.id == item_id, Task.challenge_id == challenge.id)
    ).scalar_one_or_none()


def score_mcq(
    db: Session, *, campus_id: str, student_id: int, item_id: int, answer: str
) -> ScoredResponse:
    """Auto-score an MCQ submission against its answer key (FR-E4 / US-18).

    Instant and synchronous: the score is computed, stored, and returned inside the
    submitting request — there is no job and nothing to poll for. Raises
    ``ItemNotFound`` (absent, foreign, or draft), ``NotAnMCQ``, ``UnknownOption``, or
    ``DuplicateResponse``.
    """
    item = _item_in_active_challenge(db, campus_id=campus_id, item_id=item_id)
    if item is None:
        raise ItemNotFound

    # An AssessmentItem holds both types. A reflection has a NULL answer_key, so
    # falling through would score every reflection incorrect rather than refusing.
    if item.item_type != MCQ_ITEM_TYPE or item.answer_key is None:
        raise NotAnMCQ

    options = list(item.options or [])
    # Refuse rather than score 0.0. A tampered payload or client bug must not become
    # a permanent zero — the one-attempt constraint would leave no way back from it.
    if answer not in options:
        raise UnknownOption

    existing = db.execute(
        select(AssessmentResponse).where(
            AssessmentResponse.student_id == student_id,
            AssessmentResponse.assessment_item_id == item.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicateResponse

    correct = answer == item.answer_key
    score = CORRECT_SCORE if correct else INCORRECT_SCORE

    db.add(
        AssessmentResponse(
            student_id=student_id,
            assessment_item_id=item.id,
            response=answer,
            score=score,
            scored_by="auto",
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        # Two submissions racing the check above; the constraint is the real arbiter.
        db.rollback()
        raise DuplicateResponse from exc

    return ScoredResponse(
        item_id=item.id,
        outcome_tag=item.outcome_tag,
        response=answer,
        score=score,
        correct=correct,
        correct_option=item.answer_key,
        scored_by="auto",
    )
