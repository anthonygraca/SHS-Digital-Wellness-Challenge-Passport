from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# A chat turn is a question, not an essay — a quarter of MAX_REFLECTION_CHARS. It matters
# for the same two reasons the reflection cap does: an unbounded write, and an unbounded
# token bill payable by anyone with a session once US-16 puts a model behind the seam.
# Enforced here so an abusive payload 422s before the route body runs and never reaches
# the guide at all.
MAX_GUIDE_MESSAGE_CHARS = 2000


class GuideMessageIn(BaseModel):
    """Body for one message to the wellness guide (FR-E3).

    Known leak, accepted rather than fixed on this branch: FastAPI's default
    ``RequestValidationError`` handler serializes pydantic's error dicts, which carry an
    ``input`` key — so a blank or overlong message is echoed back in the 422 body. That
    is the one place services/guide_safety.py's "the message text does not leave this
    request" claim is untrue. It is currently theoretical: nothing logs response bodies
    and the echo goes only to the browser that sent it. The fix is an exception handler
    scoped to /api/guide, which changes the error shape app-wide to address a
    path-specific concern — a follow-up, not a prerequisite.
    """

    message: str = Field(..., min_length=1, max_length=MAX_GUIDE_MESSAGE_CHARS)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        # min_length alone accepts "   ", which would reach the detectors as a message
        # with no words and match nothing — an out-of-scope deflection for a student who
        # said nothing, which reads as the guide refusing them.
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class CrisisResourceOut(BaseModel):
    """One place a student in crisis can reach a person (FR-E3 / NFR-8).

    ``role`` exists so that neither the UI nor a test has to key off a phone number or a
    name. Both of those are per-campus deploy config (NFR-4, see config.py) — an
    assertion on "(661) 654-3366" breaks the day a campus overrides it, and an assertion
    on the prose breaks the day someone rewrites the headline. ``role`` is the only field
    here that is invariant across every deploy, which makes it the only thing the US-17
    acceptance tests can safely bind to.

    Same reasoning as ``ReflectionResultOut.outcomeTag`` (schemas/assessment.py):
    structured data travels as its own field so the UI renders it as an element rather
    than parsing it back out of prose. Here the stakes are higher than a bolded word —
    the UI needs ``phone`` verbatim to build a ``tel:`` href, and a number scraped out of
    a sentence is a number that can be scraped wrong.
    """

    role: Literal["lifeline", "campus_counseling", "shs_front_desk"]
    name: str
    phone: str
    detail: str | None = None


class CrisisResourcesOut(BaseModel):
    """The hard-coded crisis card: a headline and the people to call.

    ``resources`` is ordered, lifeline first, and the UI must not re-sort it.
    """

    headline: str
    resources: list[CrisisResourceOut]


class GuideReplyOut(BaseModel):
    """The guide's reply to one message (FR-E3 / NFR-8 / US-17).

    ``kind`` is the discriminator the UI dispatches on, mirroring ``itemType`` in
    types/assessment.ts — three renderings, chosen by a field, not by matching on prose.

    ``crisis`` is populated if and only if ``kind == "crisis"``. It is a structured
    object rather than numbers baked into ``message`` because a crisis card is the one
    screen in this app where the student needs to *press* something, not read it.

    ``refusalReason`` is populated if and only if ``kind == "refusal"``. It exists so the
    two refusals — US-17 scenario 1 ("declines to give medical advice") and scenario 3
    ("deflects rather than fabricating") — are distinguishable without asserting on
    English. They may well render identically; two outcomes that look the same but must
    be told apart is exactly the case for a field rather than a fourth ``kind``.
    """

    kind: Literal["answer", "refusal", "crisis"]
    message: str
    refusalReason: Literal["medical", "out_of_scope"] | None = None
    crisis: CrisisResourcesOut | None = None
