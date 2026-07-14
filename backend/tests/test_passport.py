from __future__ import annotations

from sqlalchemy import select

from app.models.challenge import CheckIn, Task
from app.models.student import Student
from app.services.seed import seed_demo_challenge


def _seed_challenge(db_sessionmaker):
    with db_sessionmaker() as db:
        seed_demo_challenge(db)


def _sign_in(client, subject="abc@csub.edu", affiliation="student"):
    """Sign in through the mock IdP so the client carries the session cookie."""
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _student_id(db_sessionmaker):
    with db_sessionmaker() as db:
        return db.execute(select(Student)).scalars().one().id


def _task_ids_by_week(db_sessionmaker):
    with db_sessionmaker() as db:
        tasks = db.execute(select(Task).order_by(Task.week_no)).scalars()
        return {t.week_no: t.id for t in tasks}


def _complete_weeks(db_sessionmaker, student_id, week_nos):
    task_ids = _task_ids_by_week(db_sessionmaker)
    with db_sessionmaker() as db:
        for wk in week_nos:
            db.add(CheckIn(student_id=student_id, task_id=task_ids[wk], method="manual"))
        db.commit()


def _statuses(body):
    return [w["status"] for w in body["weeks"]]


# --- US-5 requires an authenticated student -------------------------------------


def test_passport_requires_auth(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    assert client.get("/api/passport").status_code == 401


def test_passport_404_when_no_active_challenge(client):
    # Signed in, but nothing seeded → no challenge for the campus.
    _sign_in(client)
    assert client.get("/api/passport").status_code == 404


# --- US-5 scenario 1: week tiles with status (future weeks locked) --------------


def test_passport_shows_seven_tiles_first_week_available(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)

    resp = client.get("/api/passport")
    assert resp.status_code == 200
    body = resp.json()

    assert body["totalWeeks"] == 7
    assert len(body["weeks"]) == 7
    # No check-ins yet: earliest week available, all later weeks locked.
    assert _statuses(body) == ["available"] + ["locked"] * 6
    assert body["completedWeeks"] == 0
    assert body["remainingWeeks"] == 7


def test_passport_week_payload_is_camelcase(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)

    body = client.get("/api/passport").json()
    assert set(body.keys()) == {
        "challengeName",
        "theme",
        "totalWeeks",
        "completedWeeks",
        "remainingWeeks",
        "weeks",
    }
    assert body["challengeName"] == "Stranger Things Wellness Challenge"
    assert body["theme"] == "stranger-things"

    week1 = body["weeks"][0]
    assert week1 == {
        "weekNo": 1,
        "title": "Immunity Portal",
        "caption": (
            "Step through the first portal — survival starts with protection. "
            "Grab your flu shot and wellness kit."
        ),
        "activityType": "Flu shot / wellness kit",
        "location": "SHS Lawn",
        "dateStart": "2026-09-02",
        "dateEnd": "2026-09-06",
        "prize": "Wellness kit",
        "required": False,
        "status": "available",
    }


# --- US-5 scenario 2: countdown reflects completion -----------------------------


def test_passport_countdown_after_three_completions(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)
    _complete_weeks(db_sessionmaker, _student_id(db_sessionmaker), [1, 2, 3])

    body = client.get("/api/passport").json()
    assert body["completedWeeks"] == 3
    assert body["totalWeeks"] == 7
    assert body["remainingWeeks"] == 4
    # Weeks 1-3 complete, week 4 becomes available, the rest lock.
    assert _statuses(body) == ["complete"] * 3 + ["available"] + ["locked"] * 3


# --- US-5 scenario 3: countdown updates after a new completion ------------------


def test_passport_countdown_updates_on_new_completion(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)
    student_id = _student_id(db_sessionmaker)
    _complete_weeks(db_sessionmaker, student_id, [1, 2, 3])

    before = client.get("/api/passport").json()
    assert (before["completedWeeks"], before["remainingWeeks"]) == (3, 4)

    _complete_weeks(db_sessionmaker, student_id, [4])

    after = client.get("/api/passport").json()
    assert (after["completedWeeks"], after["remainingWeeks"]) == (4, 3)
    assert _statuses(after) == ["complete"] * 4 + ["available"] + ["locked"] * 2


# --- Manual check-in (event detail button + manual unlock) ----------------------


def test_checkin_requires_auth(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    assert client.post("/api/checkins", json={"weekNo": 1}).status_code == 401


def test_checkin_marks_week_complete_and_updates_counts(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)

    resp = client.post("/api/checkins", json={"weekNo": 1})
    assert resp.status_code == 200
    body = resp.json()
    # The refreshed passport comes back with week 1 complete and counts updated.
    assert body["completedWeeks"] == 1
    assert body["remainingWeeks"] == 6
    assert _statuses(body) == ["complete", "available"] + ["locked"] * 5


def test_checkin_manual_unlock_any_week(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)

    # Week 5 is normally locked; a manual check-in still completes it.
    body = client.post("/api/checkins", json={"weekNo": 5}).json()
    assert body["completedWeeks"] == 1
    assert body["weeks"][4]["status"] == "complete"


def test_checkin_is_idempotent(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)

    client.post("/api/checkins", json={"weekNo": 1})
    body = client.post("/api/checkins", json={"weekNo": 1}).json()
    # Re-tapping the same week does not double count.
    assert body["completedWeeks"] == 1
    with db_sessionmaker() as db:
        assert len(list(db.execute(select(CheckIn)).scalars())) == 1


# --- Multi-tenancy: a student only sees their own completions -------------------


def test_passport_completions_are_per_student(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client)
    # Seed a check-in for a DIFFERENT student; the signed-in student stays at zero.
    task_ids = _task_ids_by_week(db_sessionmaker)
    with db_sessionmaker() as db:
        other = Student(
            campus_id="csub", sso_subject="other@csub.edu", affiliation="student"
        )
        db.add(other)
        db.commit()
        db.add(CheckIn(student_id=other.id, task_id=task_ids[1], method="manual"))
        db.commit()

    body = client.get("/api/passport").json()
    assert body["completedWeeks"] == 0
    assert _statuses(body)[0] == "available"
