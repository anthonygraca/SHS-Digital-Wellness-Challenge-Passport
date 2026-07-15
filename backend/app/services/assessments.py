from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.challenge import AssessmentItem, AssessmentResponse, Task
from app.models.student import Student
from app.services.challenges import get_active_challenge_for_campus
from app.services.reflection_scoring import ReflectionScorer, ScoringUnavailable

# An MCQ is all-or-nothing: it has exactly one keyed option. The float range is
# shared with the FR-E5 rubric scoring, which lands between these two.
CORRECT_SCORE = 1.0
INCORRECT_SCORE = 0.0

MCQ_ITEM_TYPE = "mcq"
REFLECTION_ITEM_TYPE = "reflection"


class ItemNotFound(Exception):
    """No such item in this campus's active published challenge."""


class NotAnMCQ(Exception):
    """The item exists but is a reflection — ``score_reflection`` handles those."""


class NotAReflection(Exception):
    """The item is an MCQ, or a reflection with no rubric to score against."""


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
class ScoredReflection:
    """The outcome of scoring one reflection submission (FR-E5).

    No ``correct`` field, unlike ``ScoredResponse``: a reflection has no keyed answer,
    so a boolean here could only be a lie about a 0.6.
    """

    item_id: int
    outcome_tag: str
    response: str
    score: float
    feedback: str
    scored_by: str


@dataclass
class StoredResponseView:
    """A student's own already-stored answer to an item."""

    response: str
    score: float
    # None for a reflection: a rubric score is a matter of degree, and there is no
    # keyed answer for it to be right or wrong against.
    correct: bool | None
    scored_by: str
    # The stored FR-E5 feedback; None for every MCQ, whose feedback is composed at
    # scoring time from the answer key and never stored.
    feedback: str | None
    ts: datetime


@dataclass
class KnowledgeCheckItemView:
    """An assessment item as the student may see it — no answer key and no rubric.

    Both omissions are structural rather than filtered. ``options`` is empty for a
    reflection, which is what ``item_type`` is for.
    """

    id: int
    week_no: int
    item_type: str
    prompt: str
    outcome_tag: str
    options: list[str]
    your_response: StoredResponseView | None


def _stored_view(
    response: AssessmentResponse | None, *, item_type: str
) -> StoredResponseView | None:
    if response is None:
        return None
    return StoredResponseView(
        response=response.response,
        score=response.score,
        correct=(response.score == CORRECT_SCORE if item_type == MCQ_ITEM_TYPE else None),
        scored_by=response.scored_by,
        feedback=response.ai_feedback,
        ts=response.ts,
    )


def list_week_items(
    db: Session, *, campus_id: str, student_id: int, week_no: int
) -> list[KnowledgeCheckItemView] | None:
    """The assessment items on one week of the campus's active challenge, with answers.

    Returns ``None`` when the campus has no published challenge or has no such week —
    the caller 404s. An empty list means the week exists but carries no assessment,
    which is the common case and not an error.

    Both item types are served. Reflections were filtered out until FR-E5 gave them a
    surface to render on and a scorer to grade them with; the caller tells them apart by
    ``item_type`` rather than by guessing from an empty ``options``.
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
            .where(AssessmentItem.task_id == task.id)
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
            item_type=item.item_type,
            prompt=item.prompt,
            outcome_tag=item.outcome_tag,
            options=list(item.options or []),
            your_response=_stored_view(responses.get(item.id), item_type=item.item_type),
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


def score_reflection(
    db: Session,
    *,
    campus_id: str,
    student_id: int,
    item_id: int,
    text: str,
    scorer: ReflectionScorer,
) -> ScoredReflection:
    """Score a free-text reflection against its rubric and store it (FR-E5 / US-19).

    Synchronous like ``score_mcq``: the score comes back from the submitting request and
    there is nothing to poll. Raises ``ItemNotFound`` (absent, foreign, or draft),
    ``NotAReflection``, ``DuplicateResponse``, or ``ScoringUnavailable``.

    The scorer arrives as a parameter rather than an import. That is what keeps this
    module free of FastAPI (the router does the ``Depends``) and what lets a test swap in
    a fake without patching — the codebase has no monkeypatch anywhere, and this does not
    introduce the first one.

    Note where ``db.add`` sits: every refusal above it returns before the session is
    touched, so "a failed scoring stores nothing" is a property of the ordering rather
    than a promise the code makes. That matters because a reflection is one attempt.
    """
    item = _item_in_active_challenge(db, campus_id=campus_id, item_id=item_id)
    if item is None:
        raise ItemNotFound

    # The rubric guard mirrors score_mcq's answer_key guard: a reflection saved without
    # one would otherwise be scored against "", which is a number with no meaning rather
    # than a refusal.
    if item.item_type != REFLECTION_ITEM_TYPE or item.rubric is None:
        raise NotAReflection

    # Before scoring, not after. Once a real model is behind the seam this is a call with
    # real latency and real cost, and spending it on a submission we are about to refuse
    # is waste; worse, a scorer outage would then answer "we're down" to a student whose
    # actual answer is "you already did this".
    existing = db.execute(
        select(AssessmentResponse).where(
            AssessmentResponse.student_id == student_id,
            AssessmentResponse.assessment_item_id == item.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicateResponse

    result = scorer.score(
        prompt=item.prompt,
        rubric=item.rubric,
        outcome_tag=item.outcome_tag,
        response=text,
    )

    # Refuse rather than clamp. A scorer returning 1.4 is broken, and clamping to 1.0
    # would invent a grade and silently skew the FR-F4 per-outcome mean — a wrong number
    # that looks exactly like a right one. This check lives here rather than in a schema
    # because the scorer's output never passes through one.
    if not INCORRECT_SCORE <= result.score <= CORRECT_SCORE:
        raise ScoringUnavailable(f"Scorer returned {result.score!r}, outside 0.0..1.0")

    db.add(
        AssessmentResponse(
            student_id=student_id,
            assessment_item_id=item.id,
            response=text,
            score=result.score,
            scored_by="auto",
            ai_feedback=result.feedback,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        # Two submissions racing the check above; the constraint is the real arbiter.
        db.rollback()
        raise DuplicateResponse from exc

    return ScoredReflection(
        item_id=item.id,
        outcome_tag=item.outcome_tag,
        response=text,
        score=result.score,
        feedback=result.feedback,
        scored_by="auto",
    )


# ---------------------------------------------------------------------------
# Admin score override (FR-E5)
#
# Reached through the admin challenge/task/item chain in routers/challenges.py rather
# than through _item_in_active_challenge above: that helper is scoped to the *published*
# challenge, which is right for a student and wrong for an admin, who must be able to
# read and fix scores on a draft too.
# ---------------------------------------------------------------------------


def list_item_responses(
    db: Session, item_id: int
) -> list[tuple[AssessmentResponse, Student]]:
    """Every response to one item, paired with its student for subject display.

    Returns tuples for the same reason ``list_task_checkins`` does: the only student
    identifier the admin surface shows lives on the Student row, not this one.
    """
    rows = db.execute(
        select(AssessmentResponse, Student)
        .join(Student, Student.id == AssessmentResponse.student_id)
        .where(AssessmentResponse.assessment_item_id == item_id)
        .order_by(AssessmentResponse.ts.desc())
    ).all()
    return [(response, student) for response, student in rows]


def get_item_response(
    db: Session, item_id: int, response_id: int
) -> AssessmentResponse | None:
    """One response, scoped to the item it belongs to.

    The item_id filter is what makes a response id from another item a 404 rather than
    an override applied to the wrong question.
    """
    return db.execute(
        select(AssessmentResponse).where(
            AssessmentResponse.id == response_id,
            AssessmentResponse.assessment_item_id == item_id,
        )
    ).scalar_one_or_none()


def override_response_score(
    db: Session, response: AssessmentResponse, score: float
) -> AssessmentResponse:
    """Set a score by hand (FR-E5). ``scored_by`` becomes "human".

    ``ai_feedback`` is deliberately left alone. FR-E5 mandates no audit table — this
    field beside scored_by="human" is the entire trace the override leaves, and the two
    answer different questions: whether the score is the machine's, and what the machine
    had said. Clearing it would destroy the only record of the thing overridden, and the
    student has already read it.

    The pair can read oddly — upbeat feedback beside a hand-set 0.2 — but that is a
    labelling problem for the UI, not a reason to delete evidence.
    """
    response.score = score
    response.scored_by = "human"
    db.commit()
    db.refresh(response)
    return response
