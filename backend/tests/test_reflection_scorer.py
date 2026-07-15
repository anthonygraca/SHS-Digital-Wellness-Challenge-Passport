"""Unit tests for the stub reflection scorer (US-19 / FR-E5).

No client and no database — this is the one module that tests the scorer itself rather
than the route around it. Everything here pins a property the *service* relies on and
cannot check: that the score is in range, that it is a function of the rubric, and that
the feedback does not leak the rubric.

These tests are deliberately coupled to the stub. A real scorer will not be
deterministic and will not have bands, so when one lands, this file goes with the stub
and the route tests keep working against an injected fake — which is the whole point of
the seam.
"""

from __future__ import annotations

from app.services.reflection_scoring import (
    TARGET_WORDS,
    ReflectionScore,
    StubReflectionScorer,
)

RUBRIC = (
    "Names a specific number; names a specific doable action; "
    "connects the action to the number."
)
PROMPT = "What is one number from today's labs you want to change?"
OUTCOME_TAG = "know-your-numbers"


def _score(response: str, *, rubric: str = RUBRIC) -> ReflectionScore:
    return StubReflectionScorer().score(
        prompt=PROMPT, rubric=rubric, outcome_tag=OUTCOME_TAG, response=response
    )


def test_score_is_deterministic() -> None:
    """The same input scores the same twice — what lets the BDD test assert a number.

    A real scorer breaks this, and that is expected; the tests that outlive the stub are
    the route tests, which inject their own fake.
    """
    text = "I want to change my resting heart rate by walking after dinner each day."
    assert _score(text) == _score(text)


def test_score_is_a_function_of_the_rubric() -> None:
    """Two identical reflections score differently under different rubrics.

    This is the test that makes FR-E5's "scored against the rubric" observable rather
    than aspirational. A length-only scorer would pass everything else in this file and
    fail this one.
    """
    text = "I will lower my cholesterol number by cooking at home three nights a week."
    on_topic = _score(text, rubric="cholesterol cooking number lower")
    off_topic = _score(text, rubric="sunscreen dermatology melanoma screening")
    assert on_topic.score > off_topic.score


def test_more_rubric_overlap_scores_higher() -> None:
    """Monotone in coverage — what makes the signal defensible rather than arbitrary."""
    rubric = "sleep schedule caffeine screens bedtime"
    padding = " and I think this matters quite a lot for how I feel every single day."
    covers_two = _score("My sleep schedule is poor." + padding, rubric=rubric)
    covers_four = _score(
        "My sleep schedule is poor, caffeine and screens both hurt my bedtime." + padding,
        rubric=rubric,
    )
    assert covers_four.score > covers_two.score


def test_more_length_scores_higher_up_to_the_target() -> None:
    """Monotone in effort, too — until it saturates."""
    short = _score("I will walk more.")
    longer = _score("I will walk more. " * 10)
    assert longer.score > short.score


def test_the_length_signal_saturates() -> None:
    """Past TARGET_WORDS, writing more buys nothing — padding is not effort."""
    at_target = _score("number action " * TARGET_WORDS)
    way_past = _score("number action " * TARGET_WORDS * 5)
    assert at_target.score == way_past.score


def test_a_rubric_with_no_content_words_falls_back_to_length() -> None:
    """Coverage would be 0/0. Fall back rather than divide by zero or invent a 0.5.

    Reachable in practice: an admin can save a rubric of "It is what it is." — every
    token is a stopword or under MIN_WORD_CHARS.
    """
    empty_rubric = _score("I will do the thing. " * 30, rubric="it is a to be the and")
    assert empty_rubric.score == 1.0  # effort saturated, at full weight

    assert _score("", rubric="it is a to be the and").score == 0.0


def test_score_stays_in_range_for_pathological_input() -> None:
    """The service 503s on out-of-range output, so the stub must never trip it."""
    cases = [
        "",
        "   ",
        "\n\t\n",
        "word " * 10_000,
        RUBRIC,  # the rubric quoted back verbatim — maximum coverage
        "café über naïve résumé 数字 действие",
        "!@#$%^&*()",
        "1234567890",
    ]
    for text in cases:
        result = _score(text)
        assert 0.0 <= result.score <= 1.0, f"{text[:30]!r} scored {result.score}"


def test_quoting_the_rubric_back_beats_thinking() -> None:
    """Pinning the stub's central weakness, so it is recorded rather than discovered.

    Parroting the rubric earns perfect coverage; a genuine reflection of the same length
    that happens not to reuse the vocabulary earns none. This is exactly what the class
    docstring admits to and what a real grader would punish. The test exists to make the
    limitation visible in the suite: when a model lands behind the seam, this test should
    start failing, and that failure is the good news.

    Both texts are the same word count, so effort is held constant and only coverage
    moves — otherwise this would be measuring length and proving nothing.
    """
    parroted = (
        "Names a specific number; names a specific doable action; connects them today."
    )
    thoughtful = "My blood pressure was higher than expected and I booked a recheck."
    assert len(parroted.split()) == len(thoughtful.split())

    # 0.6 against 0.1: the reflection that says something real scores a sixth of the
    # one that says nothing but the rubric's own words back.
    assert _score(parroted).score > _score(thoughtful).score


def test_feedback_never_quotes_the_rubric() -> None:
    """The rubric must not leak through the prose — the router cannot see inside to check.

    A student has one attempt, so a rubric term in the feedback tells them what they
    should have written at the moment they can no longer write it. It buys nothing and
    leaks the item.
    """
    rubric_words = {"specific", "number", "action", "connects", "doable"}
    for text in ("", "I will walk more.", RUBRIC, "word " * 200):
        feedback_words = set(_score(text).feedback.lower().replace(".", "").split())
        assert not (feedback_words & rubric_words)


def test_feedback_is_short() -> None:
    """FR-E5 says "short feedback"; the UI renders it in a callout, not a page."""
    for text in ("", "I will walk more.", "word " * 200):
        assert len(_score(text).feedback) <= 200


def test_every_band_is_reachable() -> None:
    """All three prose bands are live — a band nothing can hit is dead code.

    The three inputs bracket the 0.40 and 0.75 floors (they score ~0.05 / ~0.49 / ~0.78).
    Asserting the bands are *distinct* rather than asserting the exact prose keeps the
    copy editable without touching this test.
    """
    brief = _score("I will walk more after dinner.")
    middling = _score(
        "I want to change my cholesterol number, so my action is cooking at home three "
        "nights a week instead of eating out, which feels doable for me right now."
    )
    strong = _score(
        RUBRIC + " My number is my blood pressure and I will recheck it monthly after "
        "walking each evening, which feels doable."
    )

    assert brief.score < middling.score < strong.score
    assert len({brief.feedback, middling.feedback, strong.feedback}) == 3
