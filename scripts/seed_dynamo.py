#!/usr/bin/env python3
"""Seed the demo "Stranger Things" challenge into DynamoDB (one-off, idempotent).

The DynamoDB backend does not seed at cold start (unlike the SQLite path's
init_db -> seed_demo_challenge), so run this once after `sam deploy` to give the
passport real data. Idempotent: re-running is a no-op once the demo challenge exists.

Usage (from the repo root, after deploying the stack):

    export WP_DDB_TABLE_PREFIX=wp-           # must match the SAM TablePrefix
    export AWS_REGION=us-west-2              # your stack's region
    # AWS credentials from `aws configure` / env / SSO
    python scripts/seed_dynamo.py

Reuses the exact demo content from app.services.seed so the SQL and Dynamo demos match.
"""

from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))

from app.repositories.dynamo_repo import DynamoRepository  # noqa: E402
from app.schemas.challenge import ChallengeCreate, TaskCreate  # noqa: E402
from app.services.seed import (  # noqa: E402
    _DEMO_CAMPUS,
    _DEMO_NAME,
    _DEMO_SEMESTER,
    _DEMO_THEME,
    _DEMO_WEEKS,
)


def main() -> int:
    repo = DynamoRepository()

    existing = repo.find_challenge_by_identity(_DEMO_CAMPUS, _DEMO_NAME, _DEMO_SEMESTER)
    if existing is not None:
        print(f"Demo challenge already present (id={existing.id}); nothing to do.")
        return 0

    challenge = repo.create_challenge(
        _DEMO_CAMPUS,
        ChallengeCreate(
            name=_DEMO_NAME,
            semester=_DEMO_SEMESTER,
            start_date=_DEMO_WEEKS[0]["date_window_start"],
            end_date=_DEMO_WEEKS[-1]["date_window_end"],
        ),
    )
    # Apply the theme and publish (ChallengeCreate carries neither).
    repo.challenges.update_item(
        Key={"id": challenge.id},
        UpdateExpression="SET theme_id = :t",
        ExpressionAttributeValues={":t": _DEMO_THEME},
    )
    repo.publish_challenge(_DEMO_CAMPUS, challenge.id)

    for week in _DEMO_WEEKS:
        fields = {k: v for k, v in week.items() if k != "position"}
        repo.add_task(challenge.id, TaskCreate(**fields))

    print(
        f"Seeded '{_DEMO_NAME}' (id={challenge.id}) with {len(_DEMO_WEEKS)} tasks "
        f"for campus '{_DEMO_CAMPUS}'."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
