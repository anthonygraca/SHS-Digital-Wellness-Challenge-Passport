"""The wellness guide itself — the seam a model lands behind (US-16 / FR-E2).

This module is the seam, and it is deliberately the *only* thing US-16 replaces.
``answer_message`` in services/guide_safety.py takes a ``WellnessGuide`` as a parameter
and never imports one, so swapping the stub below for a real model is a change to this
file and to ``get_wellness_guide``'s one line — not to the safety layer, the route, the
schemas, or the UI.

That split is stronger here than it is for the scorer it mirrors
(services/reflection_scoring.py). There, the seam buys tidiness. Here it buys the US-17
guarantee: the guardrails cannot be weakened by the model landing, because the model
lands in a file the guardrails do not import. If a future diff needs to touch
guide_safety.py to make a model work, that diff is the bug.

Nothing here imports FastAPI, in keeping with the rest of services/. The router does
``Depends(get_wellness_guide)`` against a plain callable, the same shape ``get_db``
already has in db.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class GuideUnavailable(Exception):
    """The guide could not produce a reply. Nothing was said to the student.

    Raised for a failed call, a timeout, or an unusable response. The caller turns this
    into a 503 — and unlike ``ScoringUnavailable``'s, that 503 names 988. A student whose
    next message would have been a crisis message must not be met with a bare outage.
    """


@dataclass(frozen=True)
class GuideAnswer:
    """One guide reply: the prose shown to the student, and nothing else.

    No score, no confidence, no citations — a citation field would be a promise this
    branch cannot keep, since there is no corpus to cite (services/guide_corpus.py). When
    US-16 lands retrieval it may widen this; widening a frozen dataclass is cheap, and
    shipping a field that is always ``None`` teaches the UI to ignore it.
    """

    message: str


class WellnessGuide(Protocol):
    """Answers one in-scope wellness question.

    Implementations MUST raise ``GuideUnavailable`` for every failure they can
    anticipate — a network error, a timeout, a refusal, an unparseable response. The
    calling service deliberately does not catch ``Exception``: doing so would turn our
    own ``TypeError`` into a student-facing 503 and hide the bug forever. The cost of
    that choice is that a sloppy implementation leaks a 500, which is the louder and more
    honest failure.

    An implementation is called ONLY for a message that has already cleared the crisis,
    medical, and grounding checks in services/guide_safety.py. It is therefore never
    responsible for crisis routing, and must not attempt it: a model that helpfully
    appends its own crisis number is a model that can also get the number wrong, and
    NFR-8 says that decision is not the model's to make. ``answer_message`` reaches this
    Protocol only after every safety branch has already returned.

    ``topic`` is the guide_corpus slug the message matched. On this branch it is a hint;
    in US-16 it is the retrieval key. Either way an implementation must treat it as the
    *only* sanctioned subject of the answer.
    """

    def reply(self, *, message: str, topic: str, persona: str) -> GuideAnswer:
        """Raises ``GuideUnavailable`` if no reply can be produced."""
        ...


# Per topic slug in services/guide_corpus.py. Not answers — signposts. See the class
# docstring below for why this stub says so little.
_TOPIC_SIGNPOSTS: dict[str, str] = {
    "sleep": "sleep and rest",
    "nutrition": "eating and hydration",
    "movement": "movement and activity",
    "stress": "stress and mindfulness",
    "vision": "vision and screen time",
    "know_your_numbers": "knowing your numbers",
    "immunization": "immunizations",
    "shs_services": "what Student Health Services offers",
    "challenge": "the wellness challenge",
}


class StubWellnessGuide:
    """A deterministic placeholder. Not AI, and not an answer.

    It does not read the message. It looks the matched topic up in a table and says, in
    effect, "that is a thing SHS has content about, and I cannot tell you what the
    content says." That is the honest extent of what this branch can do: there is no
    model and no corpus (services/guide_corpus.py), so any sentence with actual wellness
    advice in it would be advice this repo invented and attributed to SHS.

    It is tempting to make the stub *say something* — a sleep-hygiene tip is easy to
    write and would demo better. That would be the one thing US-17 exists to prevent,
    dressed as helpfulness: content presented to a student as SHS-grounded that no
    clinician cleared. The 20-20-20 tip in routers/passport.py is a hard-coded stand-in
    on a screen that promises a tip; this is a guide that promises grounding, and there
    is nothing to ground it in yet. So it declines to invent, which is also exactly what
    US-17 scenario 3 asks of the pipeline as a whole.

    It exists so the vertical slice — ask, intercept, refuse, deflect, route, reply — is
    complete and testable before a model is wired in behind ``WellnessGuide``. It is
    deterministic precisely so the tests can assert on it; a real guide will not be, and
    the tests that pin this text will move behind an injected fake when it lands.
    """

    def reply(self, *, message: str, topic: str, persona: str) -> GuideAnswer:
        """Reply about ``topic``. ``message`` is ignored — see the class docstring.

        ``message`` and ``persona`` are in the signature because a real guide needs both,
        and widening a Protocol later would break every implementation of it.
        """
        signpost = _TOPIC_SIGNPOSTS.get(topic, "campus wellness")
        return GuideAnswer(
            message=(
                f"That sounds like a question about {signpost}, which is something "
                f"Student Health Services covers. I can't answer it yet — the {persona} "
                "isn't connected to SHS's content, so anything I said would be my own "
                "invention rather than theirs. Your challenge weeks have SHS-written "
                "material on this, and the SHS front desk can answer it properly."
            )
        )


# Stateless, so one instance serves every request — the same reasoning as the cached
# get_settings(). A real client will want to reuse its connection pool anyway.
_STUB = StubWellnessGuide()


def get_wellness_guide() -> WellnessGuide:
    """The guide the app runs with. Overridden in tests via app.dependency_overrides."""
    return _STUB
