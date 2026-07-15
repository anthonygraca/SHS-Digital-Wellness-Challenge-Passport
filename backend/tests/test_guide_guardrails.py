"""Route edges for the guide guardrails (FR-E3 / NFR-8 / US-17).

The acceptance scenarios live in test_guide_guardrails_bdd.py and the detectors are
unit-tested in test_guide_safety.py. This file covers what the Gherkin does not say but
the design decided: the pipeline's ordering, the absence of storage, the absence of
preconditions, the 503, and the NFR-4 per-campus override.

Several tests here exist to fail if a specific decision is quietly reversed later. Each
one names the decision in its docstring, because a test that only asserts is a test the
next person deletes.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.config import Settings, get_settings
from app.main import app
from app.models.engagement import GuideSession
from app.schemas.guide import MAX_GUIDE_MESSAGE_CHARS
from app.services.guide import GuideAnswer, GuideUnavailable, get_wellness_guide
from app.services.guide_safety import looks_like_crisis, looks_like_medical_request

STUDENT = "s1@csub.edu"
ADMIN = "admin@csub.edu"

IN_CORPUS_MESSAGE = "Any tips for sleeping better during finals?"
CRISIS_MESSAGE = "I want to kill myself."


def _sign_in_as(client, affiliation: str, subject: str) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


class _CountingGuide:
    def __init__(self, message: str = "A tip about sleep.") -> None:
        self.calls = 0
        self._message = message

    def reply(self, *, message: str, topic: str, persona: str) -> GuideAnswer:
        self.calls += 1
        return GuideAnswer(message=self._message)


class _RaisingGuide:
    def reply(self, *, message: str, topic: str, persona: str) -> GuideAnswer:
        raise GuideUnavailable("provider is down")


@pytest.fixture
def student(client) -> Iterator[None]:
    """A signed-in student. Deliberately not enrolled and with no challenge published."""
    _sign_in_as(client, "student", STUDENT)
    yield
    app.dependency_overrides.pop(get_wellness_guide, None)
    app.dependency_overrides.pop(get_settings, None)


def _post(client, message: str):
    return client.post("/api/guide/messages", json={"message": message})


# ---------------------------------------------------------------------------
# Auth and payload
# ---------------------------------------------------------------------------


def test_an_unsigned_message_is_401(client):
    assert _post(client, IN_CORPUS_MESSAGE).status_code == 401


def test_a_staff_session_is_403(client):
    """The guide is a student surface. Staff have SHS; they do not need a chatbot."""
    _sign_in_as(client, "staff", ADMIN)
    assert _post(client, IN_CORPUS_MESSAGE).status_code == 403


def test_crisis_resources_require_a_session(client):
    assert client.get("/api/guide/crisis-resources").status_code == 401


@pytest.mark.parametrize("message", ["", "   ", "\n\t "])
def test_a_blank_message_is_422(client, student, message):
    assert _post(client, message).status_code == 422


def test_an_overlong_message_is_422_and_never_reaches_the_guide(client, student):
    """The cap 422s before the route body runs, so the guide is never called.

    Today that saves a stub a wasted call. Once US-16 puts a model behind the seam it is
    also the token bill, payable by anyone holding a student session.
    """
    fake = _CountingGuide()
    app.dependency_overrides[get_wellness_guide] = lambda: fake

    resp = _post(client, "sleep " * MAX_GUIDE_MESSAGE_CHARS)

    assert resp.status_code == 422
    assert fake.calls == 0


# ---------------------------------------------------------------------------
# Pipeline ordering — see services/guide_safety.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "what dosage of ibuprofen would kill me?",
        "how many mg of tylenol to end my life?",
        "should i take enough pills to end it all?",
    ],
)
def test_a_dosage_question_that_is_also_a_crisis_routes_to_crisis(
    client, student, message
):
    """The single most important test in this file.

    Each message trips *both* detectors — a dosage request and a self-harm signal. A
    pipeline that runs the medical check first answers with "I can't advise on dosages —
    please contact SHS", which is a correct refusal and a catastrophic reply. The crisis
    check must win every tie, which is why it does not participate in ties: it runs first
    and returns.

    This test is the reason for that ordering. If you reorder answer_message and only
    this fails, nothing is wrong with the test.

    The guard below is what makes the test non-vacuous, and it is not decoration: an
    earlier draft asserted on "how many pills would kill me", which matches no medical
    phrase at all. Crisis caught it either way, so the test passed under a deliberately
    reversed pipeline and proved nothing. If a message here stops matching the medical
    detector, this test silently stops testing ordering — so it asserts that precondition
    rather than assuming it.
    """
    assert looks_like_medical_request(message), (
        "this message no longer trips the medical detector, so it cannot detect a "
        "medical-before-crisis reordering — pick another message"
    )
    assert looks_like_crisis(message)

    fake = _CountingGuide()
    app.dependency_overrides[get_wellness_guide] = lambda: fake

    body = _post(client, message).json()

    assert body["kind"] == "crisis", body
    assert body["refusalReason"] is None
    assert body["crisis"] is not None
    assert fake.calls == 0


def test_a_dose_question_naming_no_known_phrase_is_still_medical(client, student):
    """ "How many tablets of tylenol is safe?" matches no entry in _MEDICAL_PHRASES.

    The drug name is the variable part, so a phrase list cannot catch it and
    _DOSE_QUESTION_RE does. Without that regex this deflects as out-of-scope — still
    refused, but it sends a student asking about a real medication to "I only cover
    campus wellness topics" rather than to a clinician.
    """
    body = _post(client, "how many tablets of tylenol is safe?").json()

    assert body["kind"] == "refusal", body
    assert body["refusalReason"] == "medical", body


def test_a_hydration_question_is_not_a_dosage_question(client, student):
    """The bound on _DOSE_QUESTION_RE: "how much" alone must not refuse.

    A guide that refuses "how much water should I drink" is a guide nobody opens, and a
    guide nobody opens routes nobody to crisis resources.
    """
    app.dependency_overrides[get_wellness_guide] = lambda: _CountingGuide()

    body = _post(client, "how much water should i drink during a workout?").json()

    assert body["kind"] == "answer", body


def test_a_crisis_message_outside_the_corpus_still_routes_to_crisis(client, student):
    """A crisis message matches no wellness topic — that must not deflect it.

    A grounding-first pipeline replies to a self-harm disclosure with "I can only help
    with wellness topics from SHS content." Crisis runs before grounding so that the one
    message that is guaranteed to be off-topic is the one message never deflected.
    """
    body = _post(client, CRISIS_MESSAGE).json()
    assert body["kind"] == "crisis", body


def test_a_crisis_message_works_with_no_published_challenge(client, student):
    """No enrollment, no challenge, no student row beyond sign-in — still routed.

    The safety path has no preconditions, which is *why* the route takes no ``db`` and
    writes no ``GuideSession`` (whose challenge_id is nullable=False). A student at a
    campus that has published nothing is exactly the student least served by this app and
    no less likely to be in crisis.
    """
    resp = _post(client, CRISIS_MESSAGE)

    assert resp.status_code == 200, resp.text
    assert resp.json()["kind"] == "crisis"


def test_an_in_corpus_message_reaches_the_guide(client, student):
    """The mirror of every assertion above: the interceptors are not a blanket refusal.

    Without this, a pipeline that returned a refusal for literally everything would pass
    the whole safety suite.
    """
    fake = _CountingGuide()
    app.dependency_overrides[get_wellness_guide] = lambda: fake

    body = _post(client, IN_CORPUS_MESSAGE).json()

    assert fake.calls == 1
    assert body["kind"] == "answer", body
    assert body["message"] == "A tip about sleep."
    assert body["crisis"] is None
    assert body["refusalReason"] is None


# ---------------------------------------------------------------------------
# The post-model backstop
# ---------------------------------------------------------------------------


def test_a_guide_that_gives_dosage_advice_is_refused(client, student):
    """Step 5: the guide cleared every input check and then misbehaved anyway.

    The only test that exercises the output backstop. Its text is discarded whole rather
    than scrubbed — a partially-redacted answer is one this code has vouched for.
    """
    app.dependency_overrides[get_wellness_guide] = lambda: _CountingGuide(
        "Take 800 mg of ibuprofen every four hours."
    )

    body = _post(client, IN_CORPUS_MESSAGE).json()

    assert body["kind"] == "refusal", body
    assert body["refusalReason"] == "medical"
    assert "800" not in body["message"]
    assert "ibuprofen" not in body["message"]


def test_a_guide_that_asserts_a_diagnosis_is_refused(client, student):
    app.dependency_overrides[get_wellness_guide] = lambda: _CountingGuide(
        "You have insomnia and should start taking melatonin."
    )

    body = _post(client, IN_CORPUS_MESSAGE).json()

    assert body["kind"] == "refusal", body
    assert body["refusalReason"] == "medical"
    assert "melatonin" not in body["message"]


# ---------------------------------------------------------------------------
# Outage
# ---------------------------------------------------------------------------


def test_a_guide_failure_is_503_that_names_988(client, student):
    """Unlike the scorer's 503, this one carries the lifeline.

    A student whose next message would have been the crisis message must not be met with
    a bare "unavailable". The outage must not be the thing that swallows it.
    """
    app.dependency_overrides[get_wellness_guide] = lambda: _RaisingGuide()

    resp = _post(client, IN_CORPUS_MESSAGE)

    assert resp.status_code == 503
    assert "988" in resp.json()["detail"]


def test_a_crisis_message_is_unaffected_by_a_dead_guide(client, student):
    """The seam being down cannot break crisis routing, because it is not in that path."""
    app.dependency_overrides[get_wellness_guide] = lambda: _RaisingGuide()

    resp = _post(client, CRISIS_MESSAGE)

    assert resp.status_code == 200, resp.text
    assert resp.json()["kind"] == "crisis"


# ---------------------------------------------------------------------------
# Storage and privacy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [CRISIS_MESSAGE, "what dosage of ibuprofen should i take", IN_CORPUS_MESSAGE],
    ids=["crisis", "refusal", "answer"],
)
def test_nothing_is_stored(client, student, db_sessionmaker, message):
    """No GuideSession row, on any path. This is a decision made executable.

    The count is 0 because routers/guide.py has no ``db`` to write with, and this test
    fails the day someone gives it one — at which point they must answer what happens to
    a student whose campus has published no challenge (GuideSession.challenge_id is
    nullable=False), and whether SHS consented to holding a durable link between a named
    student and the act of consulting a health guide. Neither question has an answer yet;
    both belong to US-16.
    """
    assert _post(client, message).status_code == 200

    with db_sessionmaker() as db:
        assert db.query(GuideSession).count() == 0


def test_the_message_is_not_echoed_back(client, student):
    """The student's words do not leave the request (services/guide_safety.py).

    Scoped to the reply body, which is where an "I hear you said X" empathy flourish
    would land. The known 422 echo is documented on GuideMessageIn and is out of scope
    here.
    """
    secret = "zylophonic despair about kill myself and my roommate Priya"

    body = _post(client, secret).text

    assert "zylophonic" not in body
    assert "Priya" not in body


# ---------------------------------------------------------------------------
# NFR-4: per-campus deploys override the numbers
# ---------------------------------------------------------------------------


def _settings_with_other_campus() -> Settings:
    return Settings(
        campus_counseling_name="Other Campus Counseling",
        campus_counseling_phone="(555) 555-0199",
        shs_front_desk_name="Other SHS Desk",
        shs_front_desk_phone="(555) 555-0198",
    )


def test_campus_numbers_come_from_settings(client, student):
    """ "Overridable via WP_* env" is a claim; this is what makes it a fact.

    Injected through the dependency rather than the lru_cache'd get_settings(), which is
    why routers/guide.py takes ``Depends(get_settings)`` instead of importing it.
    """
    app.dependency_overrides[get_settings] = _settings_with_other_campus

    body = _post(client, CRISIS_MESSAGE).json()
    by_role = {r["role"]: r for r in body["crisis"]["resources"]}

    assert by_role["campus_counseling"]["phone"] == "(555) 555-0199"
    assert by_role["shs_front_desk"]["name"] == "Other SHS Desk"

    # role survives the override — it is the only field a test or a UI may key off.
    assert list(by_role) == ["lifeline", "campus_counseling", "shs_front_desk"]


def test_the_lifeline_is_not_overridable(client, student):
    """988 is national, so it is a constant and not config — see config.py.

    A campus that overrides its own numbers still gets 988, because there is no setting
    that could have got it wrong.
    """
    app.dependency_overrides[get_settings] = _settings_with_other_campus

    body = _post(client, CRISIS_MESSAGE).json()
    lifeline = body["crisis"]["resources"][0]

    assert lifeline["role"] == "lifeline"
    assert lifeline["phone"] == "988"


# ---------------------------------------------------------------------------
# GET /crisis-resources — the affordance's payload
# ---------------------------------------------------------------------------


def test_crisis_resources_are_reachable_without_saying_anything(client, student):
    """The student-facing affordance: a phone number without a disclosure first.

    A student who already knows they need a person should not have to type a self-harm
    signal into a chatbot to be handed one — and on this branch there is no chat surface
    at all, so this is the only route by which the numbers reach anybody.
    """
    resp = client.get("/api/guide/crisis-resources")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [r["role"] for r in body["resources"]] == [
        "lifeline",
        "campus_counseling",
        "shs_front_desk",
    ]
    assert body["resources"][0]["phone"] == "988"
    assert body["headline"].strip()


def test_crisis_resources_match_the_chat_card(client, student):
    """One card, one source. The affordance and the interceptor cannot drift apart."""
    from_get = client.get("/api/guide/crisis-resources").json()
    from_chat = _post(client, CRISIS_MESSAGE).json()["crisis"]

    assert from_get == from_chat
