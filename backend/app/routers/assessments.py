from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_current_student
from app.db import get_db
from app.schemas.assessment import (
    KnowledgeCheckItemOut,
    McqResultOut,
    McqSubmit,
    StoredResponseOut,
)
from app.services.assessments import (
    DuplicateResponse,
    ItemNotFound,
    KnowledgeCheckItemView,
    NotAnMCQ,
    ScoredResponse,
    StoredResponseView,
    UnknownOption,
    list_week_items,
    score_mcq,
)

router = APIRouter(prefix="/api/assessments", tags=["assessments"])

NO_CHALLENGE_MESSAGE = "No active challenge"
ITEM_NOT_FOUND_MESSAGE = "No such knowledge check"
NOT_AN_MCQ_MESSAGE = "That item is not a multiple-choice question"
UNKNOWN_OPTION_MESSAGE = "That is not one of the options"
DUPLICATE_MESSAGE = "You already answered this question"


def _mcq_feedback(*, correct: bool, correct_option: str) -> str:
    """The message shown beside an instant MCQ result (FR-E4).

    Naming the correct option is the whole learning payload of "immediate feedback",
    and it is safe only because a response is one attempt — reveal plus retries would
    make every stored score a 1.0. Templated rather than generated: AI-authored
    feedback against a rubric is US-19 (FR-E5). Same stand-in shape as
    ``_event_qr_tip`` in passport.py.
    """
    if correct:
        return "Correct! Nice work."
    return f'Not quite — the correct answer is "{correct_option}".'


def _to_stored_response_out(view: StoredResponseView | None) -> StoredResponseOut | None:
    if view is None:
        return None
    return StoredResponseOut(
        response=view.response,
        score=view.score,
        correct=view.correct,
        scoredBy=view.scored_by,
        ts=view.ts,
    )


def _to_item_out(view: KnowledgeCheckItemView) -> KnowledgeCheckItemOut:
    return KnowledgeCheckItemOut(
        id=view.id,
        weekNo=view.week_no,
        prompt=view.prompt,
        outcomeTag=view.outcome_tag,
        options=view.options,
        yourResponse=_to_stored_response_out(view.your_response),
    )


def _to_result_out(scored: ScoredResponse) -> McqResultOut:
    return McqResultOut(
        itemId=scored.item_id,
        outcomeTag=scored.outcome_tag,
        correct=scored.correct,
        score=scored.score,
        scoredBy=scored.scored_by,
        correctOption=scored.correct_option,
        feedback=_mcq_feedback(
            correct=scored.correct, correct_option=scored.correct_option
        ),
    )


@router.get("/weeks/{week_no}/items", response_model=list[KnowledgeCheckItemOut])
def get_week_items(
    week_no: int,
    claims: dict = Depends(require_current_student),
    db: Session = Depends(get_db),
):
    """The knowledge-check questions on one week, with the student's own answers.

    Addressed by week number rather than task id: the student surface never speaks
    task ids (cf. ``CheckInRequest.weekNo``). Identity comes from the session cookie —
    401 if not signed in, 403 if the caller is not a current student (US-2 / FR-A3).
    404 when the campus has no published challenge or no such week; an empty list means
    the week simply has no knowledge check.
    """
    views = list_week_items(
        db,
        campus_id=claims["campus_id"],
        student_id=claims["student_id"],
        week_no=week_no,
    )
    if views is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=NO_CHALLENGE_MESSAGE
        )
    return [_to_item_out(v) for v in views]


@router.post(
    "/items/{item_id}/responses",
    response_model=McqResultOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_mcq(
    item_id: int,
    payload: McqSubmit,
    claims: dict = Depends(require_current_student),
    db: Session = Depends(get_db),
):
    """Auto-score an MCQ answer instantly and store it (US-18 / FR-E4).

    The score comes back from this call itself — that is what "instantly" buys, and
    there is nothing to poll. Gated on current-student eligibility (US-2 / FR-A3).
    An item from another campus or a draft challenge is 404, same as one that does not
    exist: existence is not the student's to learn. A second submission is 409 — an MCQ
    is one attempt, because the result names the correct option.
    """
    try:
        scored = score_mcq(
            db,
            campus_id=claims["campus_id"],
            student_id=claims["student_id"],
            item_id=item_id,
            answer=payload.answer,
        )
    except ItemNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ITEM_NOT_FOUND_MESSAGE
        ) from exc
    except NotAnMCQ as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=NOT_AN_MCQ_MESSAGE
        ) from exc
    except UnknownOption as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=UNKNOWN_OPTION_MESSAGE
        ) from exc
    except DuplicateResponse as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_MESSAGE
        ) from exc

    return _to_result_out(scored)
