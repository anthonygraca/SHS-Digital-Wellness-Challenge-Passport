"""What the guide is allowed to be asked about (FR-E3 / NFR-8 / US-17 scenario 3).

**This is not retrieval, and there is no corpus.** It is a keyword table standing in for
a vector index over SHS-cleared content, which does not exist because nobody has told us
which materials are cleared — architecture-plan.md §11 open question #5, "which SHS
wellness materials are cleared to ground the guide/tips?".

What it buys is real: "deflects rather than fabricating an answer" is enforced *outside*
the model, and stays outside it when a model lands. What it costs is real too — the topic
it returns is a slug, not a retrieved passage, so a message can match ``sleep`` and still
get an answer grounded in nothing. That gap closes in US-16 and only in US-16.
``match_topic`` returning a topic means "this is the kind of question SHS content covers".
It never means "here is the SHS content that answers it", and no caller may read it that
way.

An allowlist, not a blocklist. A blocklist deflects what it recognizes as bad; an
allowlist deflects everything it does not recognize as in-scope. The second is the actual
requirement, because fabrication is a language model's default failure mode — so
deflection must be the pipeline's default outcome, and being answered must be the
exception that something affirmatively matched.

Why not a ``GuideTopic`` table: the open question above is a content-clearance decision
with a real answer that does not exist yet. Modelling a vocabulary table now would ship a
schema, a migration, and an admin surface for a decision nobody has made — and US-16
replaces the whole thing with an index anyway. This file is meant to be deleted.

This module is separate from guide_safety.py on purpose. The thing US-16 deletes and the
thing US-16 must not touch cannot live in one module, or "swap the stub without touching
safety code" is a claim no reviewer can check by reading a diff.
"""

from __future__ import annotations

from app.services.guide_text import normalize_for_matching

# Topic slug -> the phrases that put a message in it. Ordered only for readability; a
# message matching two topics gets the first, and nothing downstream depends on which,
# because the slug is a hint and not an answer (see the module docstring).
#
# Every phrase must survive normalize_for_matching — lowercase, apostrophe-free, single
# spaces. Multi-word phrases are matched as phrases, so "blood pressure" does not fire on
# a message that merely contains "pressure".
GUIDE_TOPICS: dict[str, frozenset[str]] = {
    "sleep": frozenset(
        {"sleep", "sleeping", "asleep", "insomnia", "tired", "rest", "nap", "bedtime"}
    ),
    "nutrition": frozenset(
        {
            "eat",
            "eating",
            "food",
            "nutrition",
            "diet",
            "meal",
            "meals",
            "breakfast",
            "lunch",
            "dinner",
            "snack",
            "hydration",
            "hydrated",
            "water",
            "caffeine",
        }
    ),
    "movement": frozenset(
        {
            "exercise",
            "workout",
            "working out",
            "walk",
            "walking",
            "run",
            "running",
            "gym",
            "movement",
            "active",
            "steps",
            "stretch",
        }
    ),
    "stress": frozenset(
        {
            "stress",
            "stressed",
            "anxious",
            "anxiety",
            "overwhelmed",
            "burnout",
            "breathing",
            "mindfulness",
            "meditate",
            "meditation",
            "relax",
        }
    ),
    "vision": frozenset(
        {"eye", "eyes", "vision", "eye exam", "glasses", "contacts", "screen time"}
    ),
    "know_your_numbers": frozenset(
        {
            "blood pressure",
            "cholesterol",
            "bmi",
            "screening",
            "screenings",
            "labs",
            "know your numbers",
            "my numbers",
        }
    ),
    "immunization": frozenset(
        {"flu shot", "vaccine", "vaccines", "vaccination", "immunization", "booster"}
    ),
    "shs_services": frozenset(
        {
            "shs",
            "student health",
            "health center",
            "appointment",
            "clinic",
            "counseling",
            "front desk",
            "office hours",
        }
    ),
    "challenge": frozenset(
        {
            "challenge",
            "passport",
            "week",
            "task",
            "tasks",
            "check in",
            "checkin",
            "prize",
            "points",
            "badge",
            "streak",
        }
    ),
}


def match_topic(message: str) -> str | None:
    """The topic slug ``message`` falls in, or ``None`` to deflect.

    ``None`` is the default and the safe answer: it means "nothing here matched SHS's
    subject matter", which the caller turns into a deflection rather than a guess.
    """
    normalized = normalize_for_matching(message)
    for topic, phrases in GUIDE_TOPICS.items():
        if any(f" {phrase} " in normalized for phrase in phrases):
            return topic
    return None
