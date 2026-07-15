"""Scoring a free-text reflection against its rubric (US-19 / FR-E5).

This module is the seam. ``score_reflection`` in services/assessments.py takes a
``ReflectionScorer`` as a parameter and never imports one, so swapping the stub below
for a real model is a change to this file and to ``get_reflection_scorer``'s one line —
not to the service, the route, the schemas, the storage, or the UI.

Nothing here imports FastAPI, in keeping with the rest of services/. The router does
``Depends(get_reflection_scorer)`` against a plain callable, the same shape ``get_db``
already has in db.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

# Words carrying no topical signal, so their presence in both rubric and reflection
# says nothing about whether the reflection engaged with the rubric. Short tokens are
# dropped wholesale by MIN_WORD_CHARS below, which is why this list has no "a"/"is"/"to".
_STOPWORDS = frozenset(
    {
        "about",
        "also",
        "been",
        "does",
        "each",
        "from",
        "have",
        "into",
        "must",
        "over",
        "should",
        "some",
        "than",
        "that",
        "them",
        "then",
        "they",
        "this",
        "was",
        "were",
        "what",
        "when",
        "which",
        "will",
        "with",
        "would",
        "your",
    }
)

# Below this length a token is structural, not topical ("the", "and", "you").
MIN_WORD_CHARS = 4

# The word count at which the length signal saturates. Not a target students are told
# about and not a rule — just the point past which "wrote more" stops being evidence
# of anything.
TARGET_WORDS = 60

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


class ScoringUnavailable(Exception):
    """The scorer could not produce a usable score. Nothing was stored.

    Raised for a failed call, a timeout, or output outside 0.0..1.0. The caller turns
    this into a 503 and writes no response row, which matters because a reflection is
    one attempt: a student who cannot tell whether a failed submit burned it has to
    assume it did.
    """


@dataclass(frozen=True)
class ReflectionScore:
    """One scorer's verdict: a 0.0..1.0 score and the prose shown to the student."""

    score: float
    feedback: str


class ReflectionScorer(Protocol):
    """Scores one reflection against one rubric.

    Implementations MUST raise ``ScoringUnavailable`` for every failure they can
    anticipate — a network error, a timeout, a refusal, an unparseable response. The
    calling service deliberately does not catch ``Exception``: doing so would turn our
    own ``TypeError`` into a student-facing 503 and hide the bug forever. The cost of
    that choice is that a sloppy implementation leaks a 500, which is the louder and
    more honest failure.

    ``feedback`` must not quote the rubric back. It reaches a student who has one
    attempt and cannot act on it, so a rubric term in the prose is a leak that buys
    nothing.
    """

    def score(
        self, *, prompt: str, rubric: str, outcome_tag: str, response: str
    ) -> ReflectionScore:
        """Raises ``ScoringUnavailable`` if no score can be produced."""
        ...


def _content_words(text: str) -> set[str]:
    """The topical vocabulary of a string: lowercase, deduped, stopwords dropped."""
    return {
        w
        for w in (m.group().lower() for m in _WORD_RE.finditer(text))
        if len(w) >= MIN_WORD_CHARS and w not in _STOPWORDS
    }


# (floor, prose). Ordered high to low; the first floor the score clears wins.
_BANDS: tuple[tuple[float, str], ...] = (
    (0.75, "Strong reflection — it engages closely with what the prompt asks for."),
    (0.40, "A solid start. There is more to say about the specifics here."),
    (0.00, "This is quite brief. A fuller reflection gives more to work with."),
)


class StubReflectionScorer:
    """A deterministic placeholder. Not AI, and not rubric grading.

    It measures two things a real grader would treat as incidental: how much of the
    rubric's vocabulary the student happened to reuse, and how much they wrote. It
    cannot tell a thoughtful paragraph from one that quotes the rubric back at length —
    the latter scores higher. Nothing it returns is a judgement of a reflection's
    quality, and the feedback is a band lookup, not a reading.

    It exists so the vertical slice — submit, score, store, show, override — is complete
    and testable before a model is wired in behind ``ReflectionScorer``. It is
    deterministic precisely so the tests can assert on it; a real scorer will not be,
    and those tests will move behind an injected fake when it lands.

    Why rubric overlap rather than length alone: FR-E5 says a reflection is scored
    *against the rubric*, and a word count does not touch the rubric — the acceptance
    test would then be asserting something the code does not do. Overlap is a weak
    signal but it is genuinely a function of the rubric, and it is monotone (more
    relevant words scores higher, never lower), which is what makes it defensible
    rather than arbitrary.
    """

    def score(
        self, *, prompt: str, rubric: str, outcome_tag: str, response: str
    ) -> ReflectionScore:
        """Score one reflection. ``prompt`` and ``outcome_tag`` are ignored.

        Both are in the signature because a real rubric grader needs them, and widening
        a Protocol later would break every implementation of it.
        """
        rubric_words = _content_words(rubric)
        response_words = _content_words(response)

        effort = min(len(response.split()) / TARGET_WORDS, 1.0)

        if not rubric_words:
            # A rubric of nothing but stopwords and short words has no vocabulary to
            # overlap with, so coverage would be 0/0. Fall back to effort at full
            # weight rather than dividing by zero or scoring every reflection 0.5.
            score = effort
        else:
            coverage = len(rubric_words & response_words) / len(rubric_words)
            score = 0.5 * coverage + 0.5 * effort

        score = round(score, 2)
        feedback = next(prose for floor, prose in _BANDS if score >= floor)
        return ReflectionScore(score=score, feedback=feedback)


# Stateless, so one instance serves every request — the same reasoning as the cached
# get_settings(). A real client will want to reuse its connection pool anyway.
_STUB = StubReflectionScorer()


def get_reflection_scorer() -> ReflectionScorer:
    """The scorer the app runs with. Overridden in tests via app.dependency_overrides."""
    return _STUB
