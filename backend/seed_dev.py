"""Seed a published dev challenge so the enroll flow (US-3) can be exercised.

There is no admin challenge-builder UI wired for students on this branch, so the
active challenge a student joins has to be created directly. Run from backend/:

    python seed_dev.py

Idempotent — re-running does not create duplicate challenges.
"""

from __future__ import annotations

from app.db import SessionLocal, init_db
from app.services.challenges import seed_dev_challenge


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        challenge = seed_dev_challenge(db)
        print(
            f"Active challenge ready: id={challenge.id} "
            f"name={challenge.name!r} campus={challenge.campus_id} "
            f"status={challenge.status}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
