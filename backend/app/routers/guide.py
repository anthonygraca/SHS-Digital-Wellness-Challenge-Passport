from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import require_current_student
from app.config import Settings, get_settings
from app.schemas.guide import (
    CrisisResourcesOut,
    GuideMessageIn,
    GuideReplyOut,
)
from app.services.guide import GuideUnavailable, WellnessGuide, get_wellness_guide
from app.services.guide_safety import (
    CrisisCard,
    GuideReply,
    answer_message,
    crisis_resources,
)

router = APIRouter(prefix="/api/guide", tags=["guide"])

# Unlike SCORING_UNAVAILABLE_MESSAGE, this one names 988. Both are deliberately vague
# about *why* — a student can do nothing with a provider's error text, and it would leak
# how the guide is wired. But an outage must not be the thing that swallows a crisis: if
# the guide is down and this student's next message would have been the one that
# mattered, the number has to be in front of them anyway.
GUIDE_UNAVAILABLE_MESSAGE = (
    "The guide is unavailable right now. If you are in crisis, call or text 988 to reach "
    "the Suicide & Crisis Lifeline, or 911 if you are in immediate danger."
)


def _to_crisis_out(card: CrisisCard) -> CrisisResourcesOut:
    return CrisisResourcesOut.model_validate(
        {
            "headline": card.headline,
            "resources": [
                {
                    "role": r.role,
                    "name": r.name,
                    "phone": r.phone,
                    "detail": r.detail,
                }
                for r in card.resources
            ],
        }
    )


def _to_reply_out(reply: GuideReply) -> GuideReplyOut:
    return GuideReplyOut(
        kind=reply.kind,
        message=reply.message,
        refusalReason=reply.refusal_reason,
        crisis=_to_crisis_out(reply.crisis) if reply.crisis else None,
    )


@router.post("/messages", response_model=GuideReplyOut)
def post_message(
    payload: GuideMessageIn,
    claims: dict = Depends(require_current_student),
    guide: WellnessGuide = Depends(get_wellness_guide),
    settings: Settings = Depends(get_settings),
):
    """Send one message to the wellness guide (FR-E3 / NFR-8 / US-17).

    All of the interesting behaviour is in services/guide_safety.py, which decides what
    is said and never asks the guide about a crisis. This route only translates.

    **200, not 201, and no ``db``.** Both absences are deliberate and load-bearing rather
    than unfinished. Nothing is created: no transcript, no ``GuideSession`` row — see
    models/engagement.py, whose ``challenge_id`` is ``nullable=False``, which would make
    a stored chat depend on a published challenge existing. Nothing in the safety path
    may have a precondition, so the path has no storage, so the route has no session to
    store with. A 201 would be a claim about a resource that does not exist. If a future
    change adds ``db`` here, it has to answer what happens to the student whose campus
    has published nothing.

    ``claims`` is required and then unused, which is the point: the route is gated on a
    current-student session (401 unsigned, 403 otherwise) but reads no identity out of
    it, because nothing downstream is allowed to know who asked.

    Status codes: 401 unsigned · 403 not a current student · 422 blank or over
    ``MAX_GUIDE_MESSAGE_CHARS`` · 503 when the guide cannot answer. No 404 — there is
    nothing here to fail to find.
    """
    try:
        reply = answer_message(
            message=payload.message,
            guide=guide,
            settings=settings,
        )
    except GuideUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=GUIDE_UNAVAILABLE_MESSAGE,
        ) from exc

    return _to_reply_out(reply)


@router.get("/crisis-resources", response_model=CrisisResourcesOut)
def get_crisis_resources(
    claims: dict = Depends(require_current_student),
    settings: Settings = Depends(get_settings),
):
    """The crisis card, without having to say anything to get it (FR-E3 / NFR-8).

    What the student-facing affordance renders (docs/frontend-design-prompt.md: "a
    visible crisis-resources affordance"). The chat path surfaces the same card
    unprompted on a crisis signal, but a student who already knows they need a person
    should not have to type a disclosure to a chatbot to be handed a phone number — and
    on this branch there is no chat surface at all, so this is the only way the numbers
    reach anyone.

    Reads no identity from ``claims`` and touches no database, for the same reason
    ``post_message`` doesn't: opening the crisis card is not an event this app records.
    """
    return _to_crisis_out(crisis_resources(settings))
