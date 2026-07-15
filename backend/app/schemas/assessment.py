from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class McqSubmit(BaseModel):
    """Body for an MCQ submission: the option string the student chose."""

    answer: str


class StoredResponseOut(BaseModel):
    """A student's own stored answer — what makes "the score is stored" observable.

    Returned inline on the item rather than from a route of its own: the same payload
    proves persistence to the FR-E4 acceptance test and re-hydrates an already-answered
    question when the student reopens the week.
    """

    response: str
    score: float
    correct: bool
    scoredBy: str
    ts: datetime


class KnowledgeCheckItemOut(BaseModel):
    """An MCQ as the *student* may see it. Field names are camelCase for the SPA.

    Deliberately not ``AssessmentItemOut`` (schemas/challenge.py): that schema carries
    ``answer_key`` and ``rubric``, and ``TaskOut`` embeds it — safe only because every
    route serving it is admin-gated. This schema has no ``answer_key`` field at all, so
    it cannot leak one even when built from an ORM ``AssessmentItem``; an exposed key
    would make FR-E4's auto-scoring theatre. The key surfaces once, as ``correctOption``
    on ``McqResultOut``, after the one-attempt constraint has closed the item.
    """

    id: int
    weekNo: int
    prompt: str
    outcomeTag: str
    options: list[str]
    yourResponse: StoredResponseOut | None = None


class McqResultOut(BaseModel):
    """The instant auto-scoring result for one MCQ submission (FR-E4 / US-18)."""

    itemId: int
    outcomeTag: str
    correct: bool
    score: float
    scoredBy: str
    correctOption: str
    feedback: str
