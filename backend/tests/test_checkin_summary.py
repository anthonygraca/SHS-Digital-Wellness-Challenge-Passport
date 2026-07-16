"""GET /api/challenges/{cid}/tasks/{tid}/checkins/summary — the live dashboard's poll.

Two properties carry this route, and each has a reason to be asserted rather than
assumed:

1. **No identities.** The screen is projected at an event (FR-D4 / US-28). The old
   client fetched every check-in — subjects included — and rendered only the id. The
   privacy was the client's discretion; here it is the payload's shape.
2. **A conditional GET.** The screen polls every 5s for hours. An unchanged event
   must answer 304 with no body — and must be *cacheable enough* that the browser
   conditions the request in the first place, which is the half that silently does
   nothing if it is wrong.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

ADMIN = "admin@csub.edu"
STUDENT = "student@csub.edu"
REASON = "Scanner was down at the booth."


def _sign_in_as(client, affiliation: str, subject: str = ADMIN) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _setup(client):
    """An admin session with a challenge + task. Returns (challenge_id, task_id)."""
    _sign_in_as(client, "staff", ADMIN)
    challenge = client.post(
        "/api/challenges",
        json={
            "name": "Fall 2025 Wellness",
            "semester": "Fall 2025",
            "start_date": "2025-09-01",
            "end_date": "2025-12-15",
        },
    ).json()
    task = client.post(
        f"/api/challenges/{challenge['id']}/tasks",
        json={"title": "Week 2 - Nutrition", "required": True},
    ).json()
    return challenge["id"], task["id"]


def _mark(client, cid, tid, subject, ts=None):
    """Record a check-in for `subject`, minting their Student row on the way."""
    _sign_in_as(client, "student", subject)
    _sign_in_as(client, "staff", ADMIN)
    payload = {"student_subject": subject, "reason": REASON}
    if ts is not None:
        payload["ts"] = ts.isoformat()
    res = client.post(f"/api/challenges/{cid}/tasks/{tid}/checkins", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def _summary(client, cid, tid, **kw):
    return client.get(f"/api/challenges/{cid}/tasks/{tid}/checkins/summary", **kw)


def test_an_empty_task_summarizes_to_zero_and_no_rows(client):
    cid, tid = _setup(client)

    body = _summary(client, cid, tid).json()

    assert body == {"count": 0, "recent": []}


def test_the_summary_counts_and_lists_newest_first(client):
    cid, tid = _setup(client)
    base = datetime(2025, 9, 1, 10, 0, tzinfo=timezone.utc)
    for i in range(3):
        _mark(client, cid, tid, f"s{i}@csub.edu", ts=base + timedelta(minutes=i))

    body = _summary(client, cid, tid).json()

    assert body["count"] == 3
    ts = [row["ts"] for row in body["recent"]]
    assert ts == sorted(ts, reverse=True)


def test_the_recent_feed_never_carries_a_student_identity(client):
    """The point of the route. A projected screen must not receive what it must not
    show — ~200 subjects in page state on a machine pointed at a room is the leak,
    whether or not any component renders them."""
    cid, tid = _setup(client)
    _mark(client, cid, tid, STUDENT)

    res = _summary(client, cid, tid)

    assert res.json()["recent"][0].keys() == {"id", "ts", "method"}
    # Belt and braces: the subject must not appear anywhere in the payload, including
    # in a field a later refactor might add without thinking about this screen.
    assert STUDENT not in res.text


def test_the_feed_is_capped_server_side(client):
    """RECENT_LIMIT is the query's LIMIT, not a client-side slice of everything."""
    cid, tid = _setup(client)
    for i in range(9):
        _mark(client, cid, tid, f"s{i}@csub.edu")

    body = _summary(client, cid, tid).json()

    assert body["count"] == 9  # the count is of every check-in...
    assert len(body["recent"]) == 6  # ...the feed is only the newest few


def test_an_unchanged_event_sends_no_body(client):
    cid, tid = _setup(client)
    _mark(client, cid, tid, STUDENT)

    first = _summary(client, cid, tid)
    etag = first.headers["etag"]
    assert etag.startswith('W/"')

    again = _summary(client, cid, tid, headers={"If-None-Match": etag})

    assert again.status_code == 304
    assert again.content == b""
    # The validator has to survive the 304 too, or the *next* poll has nothing to
    # condition on and every other request pays for the body again.
    assert again.headers["etag"] == etag


def test_the_summary_is_revalidatable_and_never_shared(client):
    """The half that fails silently. Without `no-cache` the browser gives a response
    with no Last-Modified no heuristic freshness, never sends If-None-Match, and the
    ETag above is decoration. `private` keeps a cookie-gated answer out of CloudFront.
    """
    cid, tid = _setup(client)

    cc = _summary(client, cid, tid).headers["cache-control"]

    assert "no-cache" in cc
    assert "private" in cc


def test_a_new_checkin_breaks_the_etag(client):
    cid, tid = _setup(client)
    _mark(client, cid, tid, "first@csub.edu")
    etag = _summary(client, cid, tid).headers["etag"]

    _mark(client, cid, tid, "second@csub.edu")

    res = _summary(client, cid, tid, headers={"If-None-Match": etag})
    assert res.status_code == 200
    assert res.json()["count"] == 2


def test_a_correction_breaks_the_etag_though_the_count_is_unchanged(client):
    """Why the validator hashes the payload rather than (count, newest ts): an admin
    correcting a check-in changes neither, and a 304 here would hide the edit that
    prompted the refresh."""
    cid, tid = _setup(client)
    checkin = _mark(client, cid, tid, STUDENT)
    etag = _summary(client, cid, tid).headers["etag"]

    res = client.patch(
        f"/api/challenges/{cid}/tasks/{tid}/checkins/{checkin['id']}",
        json={"method": "staff", "reason": REASON},
    )
    assert res.status_code == 200

    res = _summary(client, cid, tid, headers={"If-None-Match": etag})
    assert res.status_code == 200
    assert res.json()["recent"][0]["method"] == "staff"


def test_the_summary_is_scoped_to_its_own_task(client):
    cid, tid = _setup(client)
    other = client.post(
        f"/api/challenges/{cid}/tasks", json={"title": "Week 3", "required": True}
    ).json()
    _mark(client, cid, tid, STUDENT)

    assert _summary(
        client,
        cid,
        other["id"],
    ).json() == {"count": 0, "recent": []}


def test_the_summary_404s_on_an_unknown_challenge_or_task(client):
    cid, tid = _setup(client)

    assert _summary(client, 9999, tid).status_code == 404
    assert _summary(client, cid, 9999).status_code == 404


def test_a_student_cannot_read_the_summary(client):
    """It is an admin screen: the count of who has checked in is not a student's."""
    cid, tid = _setup(client)
    _sign_in_as(client, "student", STUDENT)

    assert _summary(client, cid, tid).status_code == 403


def test_a_signed_out_caller_cannot_read_the_summary(client):
    cid, tid = _setup(client)
    client.cookies.clear()

    assert _summary(client, cid, tid).status_code == 401
