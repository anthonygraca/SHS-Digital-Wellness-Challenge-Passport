from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.challenge import Challenge, Task
from app.models.theme import Theme

# The re-skin presets (US-13 / FR-B4). Palettes mirror the [data-theme] token
# blocks in frontend/src/theme/tokens.css, which stay in place as the static
# fallback; these rows are what makes a theme *editable* without a deploy (NFR-6).
_SEED_THEMES: list[dict] = [
    {
        "id": "stranger-things",
        "name": "Stranger Things",
        "palette": {
            "primary": "#ff4438",
            "on-primary": "#ffffff",
            "primary-container": "#7f1710",
            "on-primary-container": "#ffdad4",
            "secondary": "#e7bdb6",
            "on-secondary": "#442925",
            "tertiary": "#e5c38d",
            "surface": "#12100f",
            "surface-container": "#201a19",
            "surface-container-high": "#2b2321",
            "on-surface": "#f1dedb",
            "on-surface-variant": "#d8c2be",
            "outline": "#a08c88",
            "outline-variant": "#534340",
            "error": "#ffb4ab",
            "on-error": "#690005",
            "error-container": "#93000a",
            "on-error-container": "#ffdad6",
            "hero-a": "#4a0f0a",
            "hero-b": "#12100f",
            "font-display": '"Oswald", system-ui, sans-serif',
        },
        "logo_url": None,
        "hero_url": None,
        "app_title": "Wellness Passport",
        "tagline": "Step through the first portal — survival starts with protection.",
        "copy_tone": "dark, retro-80s, ominous",
    },
    {
        "id": "harry-potter",
        "name": "Harry Potter",
        "palette": {
            "primary": "#7d2e2e",
            "on-primary": "#ffffff",
            "primary-container": "#ffdad5",
            "on-primary-container": "#410004",
            "secondary": "#b8860b",
            "on-secondary": "#ffffff",
            "tertiary": "#4b5320",
            "surface": "#f5ecd8",
            "surface-container": "#eee2c9",
            "surface-container-high": "#e7d9ba",
            "on-surface": "#23190b",
            "on-surface-variant": "#4f4536",
            "outline": "#817567",
            "outline-variant": "#d3c4ad",
            "error": "#b3261e",
            "on-error": "#ffffff",
            "error-container": "#f9dedc",
            "on-error-container": "#410e0b",
            "hero-a": "#7d2e2e",
            "hero-b": "#b8860b",
            "font-display": '"Cinzel", Georgia, serif',
        },
        "logo_url": None,
        "hero_url": None,
        "app_title": "Wellness Passport",
        "tagline": "Solemnly swear to look after your wellbeing.",
        "copy_tone": "whimsical, wizarding, parchment",
    },
]

# The real "Stranger Things" 7-week challenge (docs/frontend-design-prompt.md:28-33).
# Phase 1 seeds this so the passport (US-5) has real data before the admin builder
# (US-11) exists. Dates are display metadata; US-5 derives status by sequential unlock.
_DEMO_CAMPUS = "csub"
_DEMO_THEME = "stranger-things"
_DEMO_SEMESTER = "Fall 2026"
_DEMO_NAME = "Stranger Things Wellness Challenge"

_DEMO_WEEKS: list[dict] = [
    {
        "position": 1,
        "title": "Immunity Portal",
        "caption": "Step through the first portal — survival starts with protection. "
        "Grab your flu shot and wellness kit.",
        "activity_type": "Flu shot / wellness kit",
        "location": "SHS Lawn",
        "date_window_start": date(2026, 9, 2),
        "date_window_end": date(2026, 9, 6),
        "prize": "Wellness kit",
        "required": False,
    },
    {
        "position": 2,
        "title": "Vital Screenings",
        "caption": "Check your vitals before the Upside Down does it for you. "
        "A quick blood-pressure screening.",
        "activity_type": "Blood pressure",
        "location": "Student Union",
        "date_window_start": date(2026, 9, 9),
        "date_window_end": date(2026, 9, 13),
        "prize": "Reusable water bottle",
        "required": True,
    },
    {
        "position": 3,
        "title": "Labs",
        "caption": "Into the lab — glucose, cholesterol, and HIV screening. "
        "Know your numbers, know your enemy.",
        "activity_type": "Glucose · cholesterol · HIV",
        "location": "SHS Clinic",
        "date_window_start": date(2026, 9, 16),
        "date_window_end": date(2026, 9, 20),
        "prize": "$5 café voucher",
        "required": True,
    },
    {
        "position": 4,
        "title": "Signal Distortion Check",
        "caption": "Something's distorting the signal. A vision screening keeps "
        "your sights clear.",
        "activity_type": "Vision screening",
        "location": "SHS Clinic",
        "date_window_start": date(2026, 9, 23),
        "date_window_end": date(2026, 9, 27),
        "prize": "Blue-light glasses",
        "required": True,
    },
    {
        "position": 5,
        "title": "Right-Side-Up Check-up",
        "caption": "Flip back to the right side up — a full physical and STI check-up.",
        "activity_type": "Physical / STI",
        "location": "SHS Clinic",
        "date_window_start": date(2026, 9, 30),
        "date_window_end": date(2026, 10, 4),
        "prize": "Wellness tote",
        "required": True,
    },
    {
        "position": 6,
        "title": "Calm the Chaos",
        "caption": "Calm the chaos. Vinyl & Vibes: a stress-relief break to "
        "steady your mind.",
        "activity_type": "Vinyl & Vibes / stress",
        "location": "The Rink, Student Union",
        "date_window_start": date(2026, 10, 7),
        "date_window_end": date(2026, 10, 11),
        "prize": "Sticker pack",
        "required": True,
    },
    {
        "position": 7,
        "title": "Escape the Lab",
        "caption": "Escape the lab — get moving. Outrun the Demogorgon to survive.",
        "activity_type": "Exercise",
        "location": "Rec Center",
        "date_window_start": date(2026, 10, 14),
        "date_window_end": date(2026, 10, 18),
        "prize": "Grand-prize entry: scooter + helmet",
        "required": True,
    },
]


def seed_themes(db: Session) -> None:
    """Idempotently seed the re-skin presets (US-13).

    Existing rows are never overwritten: once an admin has edited a theme's
    palette or copy, those edits must survive app restarts.
    """
    for row in _SEED_THEMES:
        if db.get(Theme, row["id"]) is None:
            db.add(Theme(**row))
    db.commit()


def seed_demo_challenge(db: Session) -> Challenge | None:
    """Idempotently seed the demo Stranger Things challenge for the demo campus.

    Returns the existing or newly created challenge; a no-op if the demo challenge
    already exists, so app restarts never duplicate it.

    Matches on the demo challenge's exact identity (campus + name + semester — the
    columns of uq_challenge_campus_name_sem) rather than on campus alone: since
    US-11 an admin can author other challenges for the same campus, and those must
    neither be mistaken for the demo seed nor make this lookup ambiguous.
    """
    existing = (
        db.execute(
            select(Challenge).where(
                Challenge.campus_id == _DEMO_CAMPUS,
                Challenge.name == _DEMO_NAME,
                Challenge.semester == _DEMO_SEMESTER,
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return existing

    challenge = Challenge(
        campus_id=_DEMO_CAMPUS,
        name=_DEMO_NAME,
        theme_id=_DEMO_THEME,
        semester=_DEMO_SEMESTER,
        start_date=_DEMO_WEEKS[0]["date_window_start"],
        end_date=_DEMO_WEEKS[-1]["date_window_end"],
        status="published",
    )
    db.add(challenge)
    db.flush()  # assign challenge.id before adding tasks

    for week in _DEMO_WEEKS:
        db.add(Task(challenge_id=challenge.id, **week))

    db.commit()
    db.refresh(challenge)
    return challenge
