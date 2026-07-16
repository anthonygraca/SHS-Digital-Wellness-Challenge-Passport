"""Phrase matching for the guide's detectors and its topic allowlist.

A third module rather than a function in one of its two callers, because the
normalization and the phrase tables are a single contract: every phrase in
guide_safety.py's crisis and medical lists, and every phrase in guide_corpus.py's topic
table, is written in the shape this function produces. Change the normalizer and both
lists silently stop matching what they claim to. If this lived in guide_safety.py then
guide_corpus.py would import the safety layer; if it lived in guide_corpus.py then the
safety layer would import the module US-16 deletes. Neither is a dependency worth having,
and the shared thing is genuinely shared.

Not reused from reflection_scoring.py's ``_content_words``: that tokenizes prose into a
topical vocabulary for scoring — it drops stopwords and anything under four characters.
Run "i want to die" through it and you get ``{"want"}``. It is the right tool for
measuring overlap and precisely the wrong one for finding a phrase.
"""

from __future__ import annotations

import re

# Apostrophes are DELETED, not separated — "can't" must become "cant", one word, and not
# "can t", two. Every straight and curly variant, because a phone keyboard produces U+2019
# by default and a laptop produces U+0027, and a crisis phrase that matches only the
# laptop is a crisis phrase that misses most students.
#
# This is deleted rather than folded into _SEPARATORS below, and the difference is a bug
# that shipped in an earlier draft of this file: with the apostrophe as a separator,
# "I can't go on" normalized to " can t go on ", the phrase "cant go on" did not match it,
# and the student got a wellness tip. There is no false positive to trade off here — this
# was simply wrong.
_APOSTROPHES = re.compile(r"['‘’ʼʻ`´]")

# Every run of remaining non-alphanumeric characters, which is what separates words for
# our purposes. Digits are kept: "988" and "20 20 20" are words a student may type.
_SEPARATORS = re.compile(r"[^a-z0-9]+")


def normalize_for_matching(text: str) -> str:
    """Lowercase ``text``, reduce punctuation to spaces, and pad with a space.

    The padding is what makes ``f" {phrase} " in normalize_for_matching(msg)`` a
    word-boundary match without a regex per phrase: " grape " does not contain " rape ",
    and a phrase at the very start or end of the message still has a space on both sides.

    Consequences the phrase lists depend on, and which are why they are written the way
    they are:

    - Apostrophes are deleted rather than separated, so "can't go on", "cant go on", and
      "CAN'T GO ON!!!" all normalize to " cant go on ". Every phrase in every list is
      therefore written apostrophe-free — punctuation gets no say in whether a student is
      heard. Curly apostrophes count: a phone keyboard emits U+2019, not U+0027.
    - Hyphens and newlines are separators, so "self-harm" and "self\\nharm" both match the
      phrase "self harm".
    - Accents and non-Latin scripts are separators too, so they are dropped. That is a
      real limitation for a campus with international students, and it is not fixed here:
      the fix is a model, not a better regex.

    What does NOT match, and cannot be made to: leetspeak ("k1ll"), deliberate typos,
    unicode homoglyphs, and any language other than English. **A keyword classifier is a
    floor, not a net.** It catches the student who types plainly, which is most of them
    and is worth having, and it will never catch someone avoiding it. Do not read the
    crisis list's length as coverage.
    """
    deapostrophized = _APOSTROPHES.sub("", text.casefold())
    return f" {_SEPARATORS.sub(' ', deapostrophized).strip()} "
