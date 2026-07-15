"""The guardrails in front of the wellness guide (FR-E3 / NFR-8 / US-17).

The guide is educational, never medical. It declines diagnosis and dosage requests, it
deflects rather than inventing, and on any self-harm or urgent-crisis signal it routes to
real people — hard-coded, never left to model discretion (architecture-plan.md §6.2,
"Guardrails (non-negotiable)").

**Ordering is the guarantee.** ``answer_message`` runs three deterministic checks and
each one ``return``s. The guide is not consulted, not overridden, not second-guessed —
it is not *reached*. "Hard-coded, not left to model discretion" is therefore a property
of control flow, which a reader can verify and a test can prove, rather than a property
of a system prompt, which is neither. Three consequences of that ordering, each written
down because each is a bug someone will otherwise arrive to fix:

1. **Crisis runs before medical.** "What dosage of ibuprofen would kill me" trips both
   detectors — "dosage" and "kill me". If medical ran first that student gets "I can't
   advise on dosages — contact SHS", which is a correct refusal and a catastrophic reply.
   The crisis answer must win every tie, so it does not participate in ties: it runs
   first.
2. **Crisis runs before grounding.** A crisis message is, by construction, outside a
   wellness-education corpus — so a grounding-first pipeline answers a self-harm
   disclosure with "I can only help with wellness topics." That is the worst sentence
   this system could emit, and it is what you get for free by ordering these checks in
   the order that reads most tidily.
3. **Every deterministic check is pre-model.** Not "the model is told to refuse and we
   check its work." A model that is asked to handle crisis correctly is a model that can
   handle it incorrectly, and NFR-8 removes that possibility rather than reducing it.

**This module logs nothing, and the absence is the design.** No message text, no matched
phrase, no redacted excerpt, no length, no hash — a hash of a short message is a lookup
table, not a redaction — no student id, and no "a crisis was intercepted" event, not even
an anonymous one:

- An anonymous counter looks like the safe middle. It is not. Uvicorn's access log
  records every request with a timestamp and a client address, so a timestamped crisis
  line joins to a timestamped access line and re-identifies the student with one `grep`.
  An "anonymous" event log is only anonymous if nothing else is logged, and something
  else is always logged.
- The identified version — "student 41 disclosed self-harm at 02:14" — is the most
  sensitive record this application could hold, and it would be held with no consented
  follow-up workflow, no clinician on call, no retention policy, and nobody reading it.
  It does not help the student; it manufactures an un-actioned disclosure that SHS now
  possesses and owes a duty toward. The student is routed to 988 and to people who answer
  a phone. That is the intervention. This is a keyword classifier, not a mandated
  reporter, and the distance between those two things is exactly the distance between
  routing and recording.

If you are here to add observability, the only thing to add is a counter with no
timestamp and no request context, and you should read US-16's "minimally logged, no PHI"
scenario and talk to SHS before adding even that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import Settings
from app.services.guide import GuideAnswer, WellnessGuide
from app.services.guide_corpus import match_topic
from app.services.guide_text import normalize_for_matching

# The Suicide & Crisis Lifeline. In code rather than config (config.py explains why): it
# is national, correct for every campus, and the one number here that must not be
# misconfigurable.
LIFELINE_PHONE = "988"
LIFELINE_NAME = "988 Suicide & Crisis Lifeline"
LIFELINE_DETAIL = "Call or text, 24/7. Free and confidential."

CRISIS_HEADLINE = "You're not alone"
CRISIS_MESSAGE = (
    "You matter, and you don't have to handle this alone. Please reach out right now — "
    "these are free, confidential, and staffed by people who want to hear from you. "
    "If you are in immediate danger, call 911."
)

MEDICAL_REFUSAL = (
    "I can't help with diagnosis, medication, or treatment — I'm an educational guide, "
    "not a clinician, and getting this wrong would matter. Please bring this to Student "
    "Health Services or another clinician who can actually examine you. The SHS front "
    "desk can get you an appointment."
)

OUT_OF_SCOPE_REFUSAL = (
    "That's outside what I can help with. I'm limited to the campus wellness topics "
    "Student Health Services covers — sleep, food, movement, stress, vision, "
    "immunizations, and your challenge — and I'd rather tell you I don't know than "
    "make something up. For anything health-related, the SHS front desk is the place "
    "to ask."
)

# Self-harm, suicide, and UC-7's "urgent-crisis signal" — which is broader than self-harm
# and deliberately includes violence a student is a victim of, since those students also
# need a person and not a wellness tip.
#
# Written in the shape normalize_for_matching produces: lowercase, apostrophe-free,
# single-spaced. Matched as padded substrings, so each entry is a whole-word phrase.
#
# Two wording rules, and the asymmetry between them is the whole design:
#   - Unambiguous tokens are bare ("suicide", "overdose", "rape"). Any use is worth a
#     card. See the module note on negation below before "fixing" that.
#   - Ambiguous ones are phrase-formed ("im not safe", never bare "unsafe"; "medical
#     emergency", never bare "emergency"). Bare "unsafe" fires on "is it unsafe to skip
#     breakfast?", which is not a hard judgement call — it is just a bad list. That is
#     the *only* concession to precision in this table. Everything else errs hot.
_CRISIS_PHRASES: frozenset[str] = frozenset(
    {
        # Suicide / self-harm
        "kill myself",
        "killing myself",
        "kill me",
        "end my life",
        "ending my life",
        "take my own life",
        "end it all",
        "suicide",
        "suicidal",
        "want to die",
        "wanna die",
        "wish i was dead",
        "wish i were dead",
        "better off dead",
        "rather be dead",
        "hurt myself",
        "hurting myself",
        "harm myself",
        "harming myself",
        "self harm",
        "selfharm",
        "cut myself",
        "cutting myself",
        "overdose",
        "overdosing",
        "hang myself",
        "jump off",
        "no reason to live",
        "nothing to live for",
        "cant go on",
        "cant do this anymore",
        "give up on life",
        "dont want to be here anymore",
        # Urgent crisis that is not self-harm (UC-7)
        "sexual assault",
        "sexually assaulted",
        "was assaulted",
        "rape",
        "raped",
        "being abused",
        "domestic violence",
        "someone is hurting me",
        "threatened to kill",
        "im not safe",
        "i am not safe",
        "i dont feel safe",
        "medical emergency",
    }
)

# Diagnosis, dosage, and treatment requests (FR-E3). A deliberately COOLER tier than the
# crisis list, and the difference is intentional rather than an oversight.
#
# The crisis list is tuned as hot as a word list goes, because its false positive costs a
# student one screen they scroll past. This list's false positive costs the guide its
# usefulness — bare "take" refuses "can I take a walk?", and a guide nobody opens is a
# guide that routes nobody to crisis resources. So the direction of error is still
# over-refusal (giving medical advice is SHS's liability, not a UX cost), but the phrases
# are shaped so ordinary wellness talk survives being wrong.
_MEDICAL_PHRASES: frozenset[str] = frozenset(
    {
        # Dosage / medication
        "dosage",
        "dose of",
        "how much should i take",
        "how many should i take",
        "how many mg",
        "how much mg",
        "milligrams",
        "prescription",
        "prescribe",
        "prescribed",
        "refill",
        "drug interaction",
        "safe to take",
        "should i take",
        "should i stop taking",
        "can i mix",
        "antibiotics for",
        # Diagnosis
        "diagnose",
        "diagnosis",
        "do i have",
        "whats wrong with me",
        "what is wrong with me",
        "am i having a",
        "is this cancer",
        "is it cancer",
        # Treatment
        "cure for",
        "treat my",
        "treatment for",
        "how do i get rid of this",
    }
)

# "How many/how much <something> <dose noun>" — a dosage question whose drug name is the
# variable part, which is why a phrase list cannot express it. "How many tablets of
# tylenol is safe?" matches no entry in _MEDICAL_PHRASES above and would otherwise fall
# through to an out-of-scope deflection: still refused, but refused for the wrong reason
# and with the wrong prose, which sends a student asking about a real medication to "I
# only cover campus wellness topics" instead of to a clinician.
#
# Requires an explicit dose noun rather than a bare "how much ... take", so "how much
# water should I take to the gym" stays a nutrition question. The bounded gap between the
# two halves keeps it to one clause — without it, "how many people should I take to the
# pharmacy to pick up pills" matches.
_DOSE_QUESTION_RE = re.compile(
    r"\b(how many|how much)\b[^.?!]{0,40}?\b"
    r"(mg|mcg|ml|iu|pills?|tablets?|capsules?|doses?)\b",
    re.IGNORECASE,
)

# Assertion-of-diagnosis stems and dose figures, matched against the GUIDE'S OWN OUTPUT.
# Narrow on purpose, and a different list from _MEDICAL_PHRASES: running the request
# detector over an answer is a category error, because it matches question shapes ("do i
# have", "should i take") and an answer is not shaped like a question.
_ADVICE_STEMS: frozenset[str] = frozenset(
    {
        "you have",
        "youve got",
        "you probably have",
        "this is likely",
        "sounds like you have",
        "stop taking",
        "start taking",
        "double your dose",
        "you should take",
    }
)

# A bare number next to a dose unit. The one pattern here that a phrase list cannot
# express, since the number is the variable part.
_DOSE_RE = re.compile(
    r"\b\d+\s?(mg|mcg|ml|iu|tablets?|pills?|capsules?|doses?)\b", re.IGNORECASE
)

# The guide's name when no theme is resolved. US-16 passes the active challenge's persona
# ("Portal Guide" for the Stranger Things skin) — see the design mock's themeMeta.
DEFAULT_PERSONA = "wellness guide"


@dataclass(frozen=True)
class CrisisResource:
    """One place a student in crisis can reach a person. Mirrors CrisisResourceOut."""

    role: str
    name: str
    phone: str
    detail: str | None = None


@dataclass(frozen=True)
class CrisisCard:
    """The hard-coded crisis routing. Ordered: the lifeline is always first."""

    headline: str
    resources: list[CrisisResource]


@dataclass(frozen=True)
class GuideReply:
    """What the pipeline decided to say. Mirrors GuideReplyOut.

    ``crisis`` is set if and only if ``kind == "crisis"``; ``refusal_reason`` if and only
    if ``kind == "refusal"``.
    """

    kind: str
    message: str
    refusal_reason: str | None = None
    crisis: CrisisCard | None = None


def _contains_any(normalized: str, phrases: frozenset[str]) -> bool:
    return any(f" {phrase} " in normalized for phrase in phrases)


def looks_like_crisis(message: str) -> bool:
    """Whether ``message`` carries a self-harm or urgent-crisis signal.

    **Deliberately over-triggers. No negation handling, no quotation handling, no
    sentiment model.** This is the design, not a limitation of the implementation, and
    the cost matrix is not close: a false positive costs a student one screen they scroll
    past, and a false negative costs the one moment the system had. There is no tuning
    knob between those two — anything that trades the second for the first trades
    something unrecoverable for something trivial.

    The sharper argument, and the one that should stop you from adding the obvious
    negation check: **"I'm not suicidal, but..." must trigger.** Not despite being a
    negation — *because* of it. Negated and hedged disclosure is the clinical signature of
    ambivalence, and ambivalence is the population this interceptor exists for. A negation
    detector would not merely be imprecise here; it would preferentially silence exactly
    the messages that matter most, a filter tuned by construction against the people it is
    for. "My essay is about suicide prevention" triggers too, and a student who is writing
    an essay closes a card. Take the trade.

    See guide_text.normalize_for_matching for what this cannot catch — leetspeak, typos,
    any language but English. A keyword classifier is a floor, not a net. Do not read the
    length of _CRISIS_PHRASES as coverage.
    """
    return _contains_any(normalize_for_matching(message), _CRISIS_PHRASES)


def looks_like_medical_request(message: str) -> bool:
    """Whether ``message`` asks for diagnosis, dosage, or treatment (FR-E3).

    Never consulted before ``looks_like_crisis`` — see ``answer_message``. A message can
    be both, and when it is, this one's answer is the wrong one.
    """
    return _contains_any(normalize_for_matching(message), _MEDICAL_PHRASES) or bool(
        _DOSE_QUESTION_RE.search(message)
    )


def looks_like_medical_advice(text: str) -> bool:
    """Whether the guide's own output strayed into diagnosis or dosage.

    The post-model backstop, and honest about its reach: **a keyword filter on output
    cannot make an ungrounded model safe.** It catches the loudest failure — a number
    next to "mg", a flat "you have X" — and nothing subtler, and a model determined to
    give bad advice in fluent prose walks straight through it. The real defense against
    fabrication is grounding, which is US-16's job and does not exist yet
    (guide_corpus.py).

    It is here for two reasons only. It means US-16's diff contains no safety code, and
    it means an adversarial model is testable *today* against real code rather than a
    TODO. Do not mistake it for the thing keeping the guide honest.
    """
    normalized = normalize_for_matching(text)
    return _contains_any(normalized, _ADVICE_STEMS) or bool(_DOSE_RE.search(text))


def crisis_resources(settings: Settings) -> CrisisCard:
    """The hard-coded crisis card (FR-E3 / NFR-8).

    Lifeline first, always, and no caller may re-sort: 988 is the number that is staffed
    around the clock and correct regardless of which campus this is deployed for. The
    campus numbers come from settings because they are per-campus deploy config (NFR-4);
    the lifeline does not, because it is not.
    """
    return CrisisCard(
        headline=CRISIS_HEADLINE,
        resources=[
            CrisisResource(
                role="lifeline",
                name=LIFELINE_NAME,
                phone=LIFELINE_PHONE,
                detail=LIFELINE_DETAIL,
            ),
            CrisisResource(
                role="campus_counseling",
                name=settings.campus_counseling_name,
                phone=settings.campus_counseling_phone,
            ),
            CrisisResource(
                role="shs_front_desk",
                name=settings.shs_front_desk_name,
                phone=settings.shs_front_desk_phone,
            ),
        ],
    )


def _crisis_reply(settings: Settings) -> GuideReply:
    return GuideReply(
        kind="crisis",
        message=CRISIS_MESSAGE,
        crisis=crisis_resources(settings),
    )


def answer_message(
    *,
    message: str,
    guide: WellnessGuide,
    settings: Settings,
    persona: str = DEFAULT_PERSONA,
) -> GuideReply:
    """Decide what the guide says to one student message (FR-E3 / NFR-8 / US-17).

    The pipeline, in the order it must stay in — see the module docstring for why each
    step sits where it does, before moving one:

        1. crisis    -> hard-coded card. RETURN. The guide is never reached.
        2. medical   -> hard-coded refusal. RETURN. The guide is never reached.
        3. grounding -> hard-coded deflection on a miss. RETURN. The guide is never
                        reached.
        4. guide.reply(...) — only for a message that is none of the above.
        5. backstop  -> the guide's own output re-checked for advice; on a hit its text
                        is discarded, not edited.

    Raises ``GuideUnavailable`` (from the guide) — deliberately uncaught here. The router
    turns it into a 503. This function does not catch bare ``Exception`` for the reason
    ``WellnessGuide`` documents: that would turn our own ``TypeError`` into a
    student-facing 503 and hide the bug forever.

    Note what is absent: ``db``. Nothing about this is stored — no transcript, no
    ``GuideSession`` row (models/engagement.py). That is US-16's decision to make with
    SHS, and it keeps the safety path free of preconditions: a student whose campus has
    no published challenge still gets the crisis card, because there is nothing here that
    needs a challenge to exist.
    """
    if looks_like_crisis(message):
        return _crisis_reply(settings)

    if looks_like_medical_request(message):
        return GuideReply(
            kind="refusal", message=MEDICAL_REFUSAL, refusal_reason="medical"
        )

    topic = match_topic(message)
    if topic is None:
        return GuideReply(
            kind="refusal", message=OUT_OF_SCOPE_REFUSAL, refusal_reason="out_of_scope"
        )

    answer: GuideAnswer = guide.reply(message=message, topic=topic, persona=persona)

    if looks_like_medical_advice(answer.message):
        # Discarded whole rather than redacted. A partially-scrubbed answer is an answer
        # this code has vouched for, and it has no basis to.
        return GuideReply(
            kind="refusal", message=MEDICAL_REFUSAL, refusal_reason="medical"
        )

    return GuideReply(kind="answer", message=answer.message)
