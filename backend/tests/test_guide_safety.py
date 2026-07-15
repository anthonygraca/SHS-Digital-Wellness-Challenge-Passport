"""Unit tests for the guide's detectors, its corpus allowlist, and its stub (US-17).

The route lives in test_guide_guardrails.py and the acceptance scenarios in
test_guide_guardrails_bdd.py. This file tests the pieces directly, with no HTTP.

Several tests here encode doctrine rather than behaviour — they exist so that a future
contributor who disagrees with a deliberate choice has to argue with a red test and a
docstring rather than silently "fix" it. Those are named for their reasoning.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services.guide import GuideUnavailable, StubWellnessGuide, get_wellness_guide
from app.services.guide_corpus import GUIDE_TOPICS, match_topic
from app.services.guide_safety import (
    _CRISIS_PHRASES,
    crisis_resources,
    looks_like_crisis,
    looks_like_medical_advice,
    looks_like_medical_request,
)
from app.services.guide_text import normalize_for_matching

# ---------------------------------------------------------------------------
# normalize_for_matching — the contract every phrase table is written against
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Kill Myself", " kill myself "),
        ("KILL MYSELF!!!", " kill myself "),
        ("can't go on", " cant go on "),
        ("can’t go on", " cant go on "),  # curly — what a phone keyboard emits
        ("cant go on", " cant go on "),
        ("CAN'T GO ON!!!", " cant go on "),
        ("self-harm", " self harm "),
        ("self\nharm", " self harm "),
        ("  spaced   out  ", " spaced out "),
        ("", "  "),
    ],
)
def test_normalization_collapses_punctuation_and_case(raw, expected):
    """Apostrophes, case, hyphens, and newlines all vanish.

    This is why every phrase in _CRISIS_PHRASES and GUIDE_TOPICS is written lowercase and
    apostrophe-free: punctuation gets no say in whether a student is heard.
    """
    assert normalize_for_matching(raw) == expected


def test_padding_preserves_word_boundaries():
    """The space padding is what makes a substring check a word-boundary check.

    Without it, "grape" contains "rape" and a student asking about fruit gets a crisis
    card. This is the cheap alternative to a regex per phrase.
    """
    assert " rape " not in normalize_for_matching("I ate a grape")
    assert " rape " in normalize_for_matching("rape")
    assert " rape " in normalize_for_matching("It was rape.")


def test_a_phrase_at_the_very_start_or_end_still_matches():
    assert " suicide " in normalize_for_matching("suicide")


@pytest.mark.parametrize(
    "message",
    [
        "I can't go on",
        "I can’t go on",  # curly apostrophe, straight from a phone keyboard
        "i cant go on",
        "I can't do this anymore",
        "I don't want to be here anymore",
    ],
)
def test_an_apostrophe_does_not_defeat_the_crisis_detector(message):
    """A regression test for a bug that was real, not a hypothetical.

    An earlier draft treated the apostrophe as a word separator, so "I can't go on"
    normalized to " can t go on " and the phrase "cant go on" did not match it. The
    student got a wellness tip. Every phrase in _CRISIS_PHRASES containing a contraction
    was dead on arrival for anyone who types properly — and on a phone, that is the
    default, since iOS and Android autocorrect a straight quote to a curly one.

    This is the failure mode of a keyword list: it fails silently and looks fine. The
    parametrized table test above proves each phrase matches *itself*; this proves the
    phrases match what a student actually types.
    """
    assert looks_like_crisis(message)


# ---------------------------------------------------------------------------
# The crisis detector
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phrase", sorted(_CRISIS_PHRASES))
def test_every_crisis_phrase_triggers(phrase):
    """The table cannot rot into decoration.

    A phrase added in the wrong shape — capitalised, apostrophe'd, padded — silently
    matches nothing, and the failure mode of a safety list that silently matches nothing
    is that nobody notices. This is the test that notices.
    """
    assert looks_like_crisis(f"hey, {phrase} and I don't know what to do")


def test_a_negated_disclosure_still_triggers():
    """Not a false positive we tolerate — the case the interceptor is *for*.

    Negated and hedged disclosure is the clinical signature of ambivalence, and
    ambivalence is the population this exists for. A negation detector would not merely
    be imprecise; it would preferentially silence exactly the messages that matter most.
    See looks_like_crisis.__doc__ before "fixing" this.
    """
    assert looks_like_crisis("I'm not suicidal, but I've been feeling really low")
    assert looks_like_crisis("I would never kill myself, I just feel numb")


def test_an_academic_mention_of_suicide_still_triggers():
    """A student writing an essay gets a card they scroll past. That is the whole cost.

    Deliberate over-trigger. The alternative — context detection — buys a marginally
    tidier transcript and pays for it in false negatives, and a false negative here costs
    the one moment the system had.
    """
    assert looks_like_crisis("my essay is about suicide prevention programs")
    assert looks_like_crisis("we read a paper on self harm in adolescents")


def test_a_quoted_crisis_signal_still_triggers():
    """No quotation handling either, for the same reason as negation."""
    assert looks_like_crisis('my friend texted me "I want to die" and I am scared')


def test_urgent_crisis_beyond_self_harm_triggers():
    """UC-7 says "self-harm or urgent-crisis", and the second half is not the first.

    A student who was assaulted needs a person, not a wellness tip, and nothing in the
    self-harm vocabulary would catch them.
    """
    assert looks_like_crisis("I was sexually assaulted at a party last night")
    assert looks_like_crisis("my partner threatened to kill me")


@pytest.mark.parametrize(
    "message",
    [
        "is it unsafe to skip breakfast?",
        "how do I stop my eyes hurting after a long day?",
        "the gym was dead today",
        "this workout is killing my legs",
        "I ate a grape",
        "finals week is murder",
    ],
)
def test_ordinary_messages_do_not_trigger(message):
    """The bound on erring hot: bare "unsafe" and bare "emergency" are not in the table.

    "Is it unsafe to skip breakfast" firing a crisis card is not a hard judgement call —
    it is just a bad list. This is the one concession to precision the crisis table makes.
    """
    assert not looks_like_crisis(message)


def test_kill_myself_and_kill_me_are_independent_phrases():
    """Both are in the table; neither is a substring of the other under padding."""
    assert looks_like_crisis("I want to kill myself")
    assert looks_like_crisis("I want someone to kill me")


# ---------------------------------------------------------------------------
# The medical-request detector — a deliberately cooler tier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "what dosage of ibuprofen should I take?",
        "how many mg of melatonin is safe?",
        "how many tablets of tylenol is safe?",
        "can you diagnose this rash?",
        "do I have strep throat?",
        "should I stop taking my prescription?",
        "what's the cure for a sinus infection?",
    ],
)
def test_medical_requests_are_detected(message):
    assert looks_like_medical_request(message)


@pytest.mark.parametrize(
    "message",
    [
        "can I take a walk instead of the gym?",
        "how much water should I drink during a workout?",
        "how many steps a day should I aim for?",
        "how much sleep do I actually need?",
        "what should I eat before a morning class?",
    ],
)
def test_ordinary_wellness_talk_is_not_a_medical_request(message):
    """The reason "take" and a bare "how much" are not in the tables.

    This tier's false positive is not an annoyance — it is a guide that refuses ordinary
    questions, and a guide nobody opens routes nobody to crisis resources. Over-refusal
    is still the direction of error; the phrases are shaped so the guide survives being
    one.
    """
    assert not looks_like_medical_request(message)


# ---------------------------------------------------------------------------
# The output backstop
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Take 800 mg of ibuprofen every four hours.",
        "Take 800mg and lie down.",
        "You have insomnia.",
        "This is likely a migraine.",
        "You should stop taking that.",
        "Try 2 tablets before bed.",
    ],
)
def test_the_backstop_catches_loud_advice(text):
    assert looks_like_medical_advice(text)


@pytest.mark.parametrize(
    "text",
    [
        "A consistent bedtime helps more than catching up at weekends.",
        "Student Health Services can talk this through with you.",
        "Your challenge weeks have SHS-written material on this.",
        "Walking for 20 minutes after dinner is a good place to start.",
    ],
)
def test_the_backstop_passes_ordinary_prose(text):
    assert not looks_like_medical_advice(text)


def test_the_backstop_does_not_catch_question_shapes():
    """It is a different list from _MEDICAL_PHRASES, and this is why.

    Running the request detector over an answer is a category error: it matches question
    shapes, and a guide legitimately quoting a student's question back would be refused
    for it.
    """
    assert not looks_like_medical_advice("Do I have time to sleep? Most students do.")


def test_the_stub_guides_own_output_clears_the_backstop():
    """A guard against the stub tripping our own filter and refusing every answer.

    The suite would still be green — a refusal is a valid outcome — while the guide was
    incapable of answering anything.
    """
    for topic in GUIDE_TOPICS:
        answer = StubWellnessGuide().reply(
            message="whatever", topic=topic, persona="wellness guide"
        )
        assert not looks_like_medical_advice(answer.message), topic


# ---------------------------------------------------------------------------
# The corpus allowlist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "topic"),
    [
        ("any tips for sleeping better?", "sleep"),
        ("what should I eat before class", "nutrition"),
        ("is walking enough exercise", "movement"),
        ("finals have me so stressed", "stress"),
        ("my eyes hurt after screen time", "vision"),
        ("what is a good blood pressure", "know_your_numbers"),
        ("where do I get a flu shot", "immunization"),
        ("how do I book an appointment at SHS", "shs_services"),
        ("how many points is week 3 worth", "challenge"),
    ],
)
def test_in_corpus_messages_match_their_topic(message, topic):
    assert match_topic(message) == topic


@pytest.mark.parametrize(
    "message",
    [
        "who won the 1998 world cup",
        "write me a python script that reverses a list",
        "what do you think about the new parking structure",
        "asdfghjkl",
    ],
)
def test_off_corpus_messages_match_nothing(message):
    """None is the default and the safe answer.

    An allowlist deflects everything it does not recognize, which is the requirement:
    fabrication is a model's default failure, so deflection must be the pipeline's
    default outcome.
    """
    assert match_topic(message) is None


def test_a_multiword_topic_phrase_is_matched_as_a_phrase():
    """ "blood pressure" must not fire on "pressure" alone."""
    assert match_topic("I am under a lot of pressure at work") != "know_your_numbers"


# ---------------------------------------------------------------------------
# The crisis card
# ---------------------------------------------------------------------------


def test_the_card_is_lifeline_first_and_complete():
    card = crisis_resources(Settings())

    assert [r.role for r in card.resources] == [
        "lifeline",
        "campus_counseling",
        "shs_front_desk",
    ]
    assert card.resources[0].phone == "988"
    assert card.headline.strip()
    assert all(r.name.strip() and r.phone.strip() for r in card.resources)


def test_the_card_reads_campus_numbers_from_settings():
    card = crisis_resources(
        Settings(
            campus_counseling_phone="(555) 555-0199",
            shs_front_desk_phone="(555) 555-0198",
        )
    )
    by_role = {r.role: r for r in card.resources}

    assert by_role["campus_counseling"].phone == "(555) 555-0199"
    assert by_role["shs_front_desk"].phone == "(555) 555-0198"

    # Not overridable, because it is not per-campus. See config.py.
    assert by_role["lifeline"].phone == "988"


# ---------------------------------------------------------------------------
# The seam
# ---------------------------------------------------------------------------


def test_the_stub_is_deterministic():
    a = StubWellnessGuide().reply(message="tips?", topic="sleep", persona="Portal Guide")
    b = StubWellnessGuide().reply(message="tips?", topic="sleep", persona="Portal Guide")
    assert a == b


def test_the_stub_names_its_persona():
    """US-16 passes the theme's guide name ("Portal Guide"); the stub must carry it."""
    answer = StubWellnessGuide().reply(
        message="tips?", topic="sleep", persona="Portal Guide"
    )
    assert "Portal Guide" in answer.message


def test_the_stub_does_not_invent_wellness_advice():
    """The stub declines to answer, which is the honest extent of what it can do.

    A sleep-hygiene tip here would demo better and would be the exact thing US-17 exists
    to prevent, dressed as helpfulness: content presented as SHS-grounded that no
    clinician cleared. See StubWellnessGuide.__doc__.
    """
    answer = StubWellnessGuide().reply(
        message="how do I sleep better?", topic="sleep", persona="wellness guide"
    )
    assert "can't answer" in answer.message or "cannot answer" in answer.message


def test_the_provider_returns_a_usable_guide():
    """get_wellness_guide is the one line US-16 changes."""
    guide = get_wellness_guide()
    assert guide.reply(message="hi", topic="sleep", persona="guide").message.strip()


def test_the_seam_signals_failure_with_guide_unavailable():
    """The contract WellnessGuide mandates, made executable.

    Implementations MUST raise GuideUnavailable for every anticipated failure. The
    calling service deliberately does not catch bare Exception: doing so would turn our
    own TypeError into a student-facing 503 and hide the bug forever.
    """

    class _Broken:
        def reply(self, *, message: str, topic: str, persona: str):
            raise GuideUnavailable("provider is down")

    with pytest.raises(GuideUnavailable):
        _Broken().reply(message="hi", topic="sleep", persona="guide")
