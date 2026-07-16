"""GET /api/bootstrap — the SPA's one-shot first render.

The route composes /auth/session + /enrollment + /api/passport. What is worth testing
is not the composition (those three are covered in their own modules) but the contract
that makes it usable: every branch answers 200 with a *value*, including the branches
the underlying routes answer with 401/403/404, and each sub-object agrees with the
route it replaces.
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.challenge import Task
from app.services.qr import mint_event_token
from app.services.seed import seed_demo_challenge, seed_themes

STUDENT = "abc@csub.edu"


def _sign_in(client, subject=STUDENT, affiliation="student"):
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _seed(db_sessionmaker, *, themes=False):
    with db_sessionmaker() as db:
        if themes:
            seed_themes(db)
        seed_demo_challenge(db)


def _enroll(client):
    return client.post("/enrollment")


def test_signed_out_gets_three_nulls_not_a_401(client):
    """The load-bearing one: sign-in must not cost a failed request.

    Every other student route 401s here. This one is what the SPA calls before it
    knows whether anyone is signed in, so "nobody is" has to be an answer.
    """
    res = client.get("/api/bootstrap")

    assert res.status_code == 200
    assert res.json() == {"session": None, "enrollment": None, "passport": None}


def test_a_staff_session_gets_a_session_and_no_enrollment(client, db_sessionmaker):
    _seed(db_sessionmaker)
    _sign_in(client, subject="admin@csub.edu", affiliation="staff")

    body = client.get("/api/bootstrap").json()

    assert body["session"]["subject"] == "admin@csub.edu"
    assert body["session"]["isCurrentStudent"] is False
    # Staff are not participants — there is no enrollment question to answer, and the
    # SPA routes them to the builder on isAdminSession before it looks at either field.
    assert body["enrollment"] is None
    assert body["passport"] is None


def test_an_ineligible_student_gets_a_session_and_no_enrollment(client, db_sessionmaker):
    _seed(db_sessionmaker)
    _sign_in(client, affiliation="alum")

    body = client.get("/api/bootstrap").json()

    # The US-2 gate still holds: isCurrentStudent is the SPA's cue for
    # EligibilityBlocked, and no passport is built for a caller who may not have one.
    assert body["session"]["isCurrentStudent"] is False
    assert body["enrollment"] is None
    assert body["passport"] is None


def test_no_active_challenge_is_an_enrollment_answer_not_a_null(client):
    """US-3 scenario 3. `enrollment: null` means "not a student"; this student is one,
    and the honest answer is "there is nothing to join" — which the SPA renders as
    NoActiveChallenge rather than as a failure."""
    _sign_in(client)

    body = client.get("/api/bootstrap").json()

    assert body["session"]["isCurrentStudent"] is True
    assert body["enrollment"] == {"active_challenge": None, "enrolled": False}
    assert body["passport"] is None


def test_a_not_yet_enrolled_student_gets_the_join_target_and_no_passport(
    client, db_sessionmaker
):
    _seed(db_sessionmaker)
    _sign_in(client)

    body = client.get("/api/bootstrap").json()

    assert body["enrollment"]["enrolled"] is False
    assert body["enrollment"]["active_challenge"]["name"]
    # Not "no passport exists" — /api/passport would build one. The SPA is about to
    # show Join, so building it would be work for a screen nobody sees.
    assert body["passport"] is None


def test_an_enrolled_student_gets_the_whole_first_render(client, db_sessionmaker):
    _seed(db_sessionmaker, themes=True)
    _sign_in(client)
    _enroll(client)

    body = client.get("/api/bootstrap").json()

    assert body["session"]["isCurrentStudent"] is True
    assert body["enrollment"]["enrolled"] is True
    assert body["passport"]["weeks"]
    # The theme rides along, so the app skins itself on the first paint rather than
    # flashing the default and re-skinning once /api/passport lands (US-13).
    assert body["passport"]["themeConfig"] is not None


def test_the_passport_matches_what_api_passport_returns(client, db_sessionmaker):
    """One mapper, one derivation — the SPA seeds from bootstrap and then revalidates
    against /api/passport, so a difference between them would show up as a flicker."""
    _seed(db_sessionmaker, themes=True)
    _sign_in(client)
    _enroll(client)

    assert (
        client.get("/api/bootstrap").json()["passport"]
        == client.get("/api/passport").json()
    )


def test_the_enrollment_matches_what_enrollment_returns(client, db_sessionmaker):
    _seed(db_sessionmaker)
    _sign_in(client)
    _enroll(client)

    assert (
        client.get("/api/bootstrap").json()["enrollment"]
        == client.get("/enrollment").json()
    )


def test_the_session_matches_what_auth_session_returns(client, db_sessionmaker):
    _seed(db_sessionmaker)
    _sign_in(client)

    assert (
        client.get("/api/bootstrap").json()["session"]
        == client.get("/auth/session").json()
    )


def test_a_scanned_week_shows_up_in_the_bootstrap_passport(client, db_sessionmaker):
    """Derived live off the challenge this route resolved, not served from anywhere
    that could go stale: a week completed a moment ago is complete on the next open."""
    _seed(db_sessionmaker)
    _sign_in(client)
    _enroll(client)

    assert client.get("/api/bootstrap").json()["passport"]["completedWeeks"] == 0

    with db_sessionmaker() as db:
        first_week = db.execute(select(Task).order_by(Task.position)).scalars().first()
        token = mint_event_token(first_week.id)
    assert client.post("/api/checkins/scan", json={"token": token}).status_code == 200

    passport = client.get("/api/bootstrap").json()["passport"]
    assert passport["completedWeeks"] == 1
    assert passport["weeks"][0]["status"] == "complete"


def test_a_tampered_cookie_reads_as_signed_out(client):
    """A bad token is not an error to surface — it is "not signed in", the same as
    having none, so the SPA shows sign-in rather than a broken state."""
    client.cookies.set("wp_session", "not.a.real.jwt")

    res = client.get("/api/bootstrap")

    assert res.status_code == 200
    assert res.json()["session"] is None
