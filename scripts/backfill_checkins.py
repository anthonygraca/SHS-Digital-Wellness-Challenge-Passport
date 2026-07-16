#!/usr/bin/env python3
"""Backfill `id` + `challenge_id` onto pre-existing CheckIns rows (one-off, idempotent).

Why this exists
---------------
Before FR-D6 (#27) a check-in row carried only ``student_id``, ``task_id``, ``ts`` and
``method`` — enough for "has this student done this task?", which is all the passport
asks. The admin/report direction ("who has done this task / this challenge?") needs the
two new GSIs, and those need attributes the old rows do not have:

    ByTask      task_id + ts        <- old rows HAVE both, so they ARE indexed
    ByChallenge challenge_id + ts   <- old rows lack challenge_id, so they are NOT

That asymmetry is the trap. A legacy row shows up in a ByTask query but has no ``id``,
so reading it raises a KeyError — an admin opening the check-in list gets a 500 rather
than a missing row. And it never appears in any ByChallenge-backed report, silently.

Run this once after `sam deploy` of the stack that adds the indexes, BEFORE anyone uses
the admin screens. Idempotent: rows that already have both attributes are skipped, so
re-running is a no-op and a partial run can simply be repeated.

Usage (from the repo root):

    export WP_DDB_TABLE_PREFIX=wp-     # must match the SAM TablePrefix
    export WP_AWS_REGION=us-west-2     # your stack's region
    export WP_PERSISTENCE=dynamo
    # AWS credentials from `aws configure` / env / SSO
    python scripts/backfill_checkins.py            # dry run: reports, writes nothing
    python scripts/backfill_checkins.py --apply    # actually writes
"""

from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))

from app.repositories.dynamo_repo import DynamoRepository, _int  # noqa: E402


def main() -> int:
    apply = "--apply" in sys.argv
    repo = DynamoRepository()

    # A Scan, not a query: the whole point is to find rows that no index can reach.
    # One-off and offline, over a table that holds ~200 rows per challenge.
    rows: list[dict] = []
    resp = repo.checkins.scan()
    rows.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = repo.checkins.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        rows.extend(resp.get("Items", []))

    stale = [r for r in rows if "id" not in r or "challenge_id" not in r]
    print(f"checkins: {len(rows)} total, {len(stale)} needing backfill")
    if not stale:
        print("nothing to do.")
        return 0
    if not apply:
        print("dry run — re-run with --apply to write.")
        return 0

    # Resolve each row's challenge through its task, exactly as the write path does.
    task_challenge: dict[int, int] = {}
    patched = skipped = 0
    for raw in stale:
        task_id = _int(raw["task_id"])
        if task_id not in task_challenge:
            task = repo.tasks.get_item(Key={"id": task_id}).get("Item")
            if task is None:
                # The task is gone; the row can never be reported on. Leave it —
                # deleting data is not this script's call to make.
                print(f"  ! orphan check-in (task {task_id} missing), skipped")
                skipped += 1
                continue
            task_challenge[task_id] = _int(task["challenge_id"])

        raw.setdefault("id", repo._next_id("checkin"))
        raw["challenge_id"] = task_challenge[task_id]
        repo.checkins.put_item(Item=raw)
        patched += 1

    print(f"backfilled {patched} row(s); {skipped} skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
