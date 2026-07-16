from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# A reflection is prose, not an essay, and this is not a word limit anyone is asked to
# hit — it is the point past which a payload stops being a reflection. Roughly 600-700
# words, an order of magnitude beyond what the prompt invites. It matters twice: an
# unbounded textarea is an unbounded write into a Text column, and once a real model
# sits behind the scorer it is also an unbounded token bill payable by anyone with a
# session. Enforced here so an abusive payload 422s before the route body runs and
# never reaches the scorer at all.
MAX_REFLECTION_CHARS = 4000


class McqSubmit(BaseModel):
    """Body for an MCQ submission: the option string the student chose."""

    answer: str


class ReflectionSubmit(BaseModel):
    """Body for a reflection submission: the student's free text (FR-E5)."""

    text: str = Field(..., min_length=1, max_length=MAX_REFLECTION_CHARS)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        # min_length alone accepts "   ", which would burn the student's one attempt on
        # a score for nothing.
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class StoredResponseOut(BaseModel):
    """A student's own stored answer — what makes "the score is stored" observable.

    Returned inline on the item rather than from a route of its own: the same payload
    proves persistence to the FR-E4 acceptance test and re-hydrates an already-answered
    question when the student reopens the week.

    ``correct`` and ``feedback`` are each null for exactly one item type, and the
    asymmetry is honest rather than incidental: an MCQ has a keyed answer but composes
    its feedback at scoring time from that key and never stores it, while a reflection
    stores its feedback but has no keyed answer to be right or wrong against. Each type
    reports what it can actually prove.
    """

    response: str
    score: float
    correct: bool | None = None
    scoredBy: str
    feedback: str | None = None
    ts: datetime


class KnowledgeCheckItemOut(BaseModel):
    """An assessment item as the *student* may see it. camelCase for the SPA.

    Covers both item types — ``itemType`` tells them apart, and ``options`` is empty for
    a reflection. (The name predates FR-E5, when the student surface was MCQ-only. It is
    kept deliberately: see below.)

    Deliberately not ``AssessmentItemOut`` (schemas/challenge.py): that schema carries
    ``answer_key`` *and* ``rubric``, and ``TaskOut`` embeds it — safe only because every
    route serving it is admin-gated. This schema has neither field, so it cannot leak
    either one even when built from an ORM ``AssessmentItem``. An exposed key would make
    FR-E4's auto-scoring theatre; an exposed rubric would hand a student the FR-E5 mark
    scheme before they write, and the stub scorer rewards quoting it back. The key
    surfaces once, as ``correctOption`` on ``McqResultOut``, after the one-attempt
    constraint has closed the item. The rubric never surfaces at all.

    That boundary rests on nobody confusing the two schemas at a glance, which is why
    this keeps a name that reads as obviously-the-other-one rather than a tidier
    ``StudentAssessmentItemOut`` that would sit beside ``AssessmentItemOut`` as a
    near-twin.
    """

    id: int
    weekNo: int
    itemType: str
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


class ReflectionResultOut(BaseModel):
    """The scoring result for one reflection submission (FR-E5 / US-19).

    Not a variant or subclass of ``McqResultOut``, and missing both of its answer-shaped
    fields: there is no ``correctOption`` because there is no key, and no ``correct``
    because a 0.6 is neither.

    ``outcomeTag`` travels as its own field rather than baked into ``feedback`` so the UI
    can render it as an element — the mockup bolds it, and a scorer that returned
    "...Mapped to outcome: **sleep**" would be shipping markup as prose for the client to
    unpick.
    """

    itemId: int
    outcomeTag: str
    score: float
    scoredBy: str
    feedback: str
