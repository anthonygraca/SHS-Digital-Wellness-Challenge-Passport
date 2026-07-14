from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.challenge import Challenge, Task

# The real "Stranger Things" 7-week challenge (docs/frontend-design-prompt.md:28-33).
# Phase 1 seeds this so the passport (US-5) has real data before the admin builder
# (US-11) exists. Dates are display metadata; US-5 derives status by sequential unlock.
_DEMO_CAMPUS = "csub"
_DEMO_THEME = "stranger-things"
_DEMO_SEMESTER = "Fall 2026"

_DEMO_WEEKS: list[dict] = [
    {
        "week_no": 1,
        "title": "Immunity Portal",
        "caption": "Step through the first portal — survival starts with protection. "
        "Grab your flu shot and wellness kit.",
        "activity_type": "Flu shot / wellness kit",
        "location": "SHS Lawn",
        "date_start": date(2026, 9, 2),
        "date_end": date(2026, 9, 6),
        "prize": "Wellness kit",
        "is_required": False,
    },
    {
        "week_no": 2,
        "title": "Vital Screenings",
        "caption": "Check your vitals before the Upside Down does it for you. "
        "A quick blood-pressure screening.",
        "activity_type": "Blood pressure",
        "location": "Student Union",
        "date_start": date(2026, 9, 9),
        "date_end": date(2026, 9, 13),
        "prize": "Reusable water bottle",
        "is_required": True,
    },
    {
        "week_no": 3,
        "title": "Labs",
        "caption": "Into the lab — glucose, cholesterol, and HIV screening. "
        "Know your numbers, know your enemy.",
        "activity_type": "Glucose · cholesterol · HIV",
        "location": "SHS Clinic",
        "date_start": date(2026, 9, 16),
        "date_end": date(2026, 9, 20),
        "prize": "$5 café voucher",
        "is_required": True,
    },
    {
        "week_no": 4,
        "title": "Signal Distortion Check",
        "caption": "Something's distorting the signal. A vision screening keeps "
        "your sights clear.",
        "activity_type": "Vision screening",
        "location": "SHS Clinic",
        "date_start": date(2026, 9, 23),
        "date_end": date(2026, 9, 27),
        "prize": "Blue-light glasses",
        "is_required": True,
    },
    {
        "week_no": 5,
        "title": "Right-Side-Up Check-up",
        "caption": "Flip back to the right side up — a full physical and STI check-up.",
        "activity_type": "Physical / STI",
        "location": "SHS Clinic",
        "date_start": date(2026, 9, 30),
        "date_end": date(2026, 10, 4),
        "prize": "Wellness tote",
        "is_required": True,
    },
    {
        "week_no": 6,
        "title": "Calm the Chaos",
        "caption": "Calm the chaos. Vinyl & Vibes: a stress-relief break to "
        "steady your mind.",
        "activity_type": "Vinyl & Vibes / stress",
        "location": "The Rink, Student Union",
        "date_start": date(2026, 10, 7),
        "date_end": date(2026, 10, 11),
        "prize": "Sticker pack",
        "is_required": True,
    },
    {
        "week_no": 7,
        "title": "Escape the Lab",
        "caption": "Escape the lab — get moving. Outrun the Demogorgon to survive.",
        "activity_type": "Exercise",
        "location": "Rec Center",
        "date_start": date(2026, 10, 14),
        "date_end": date(2026, 10, 18),
        "prize": "Grand-prize entry: scooter + helmet",
        "is_required": True,
    },
]


def seed_demo_challenge(db: Session) -> Challenge | None:
    """Idempotently seed the demo Stranger Things challenge for the demo campus.

    Returns the existing or newly created challenge; a no-op if one already exists,
    so app restarts never duplicate it.
    """
    existing = db.execute(
        select(Challenge).where(Challenge.campus_id == _DEMO_CAMPUS)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    challenge = Challenge(
        campus_id=_DEMO_CAMPUS,
        name="Stranger Things Wellness Challenge",
        theme_id=_DEMO_THEME,
        semester=_DEMO_SEMESTER,
        starts_on=_DEMO_WEEKS[0]["date_start"],
        ends_on=_DEMO_WEEKS[-1]["date_end"],
        status="active",
    )
    db.add(challenge)
    db.flush()  # assign challenge.id before adding tasks

    for week in _DEMO_WEEKS:
        db.add(Task(challenge_id=challenge.id, **week))

    db.commit()
    db.refresh(challenge)
    return challenge
