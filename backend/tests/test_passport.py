from __future__ import annotations

from sqlalchemy import select

from app.models.challenge import Challenge, CheckIn, Task
from app.models.student import Student
from app.models.theme import Theme
from app.services.seed import seed_demo_challenge, seed_themes


def _seed_challenge(db_sessionmaker):
    with db_sessionmaker() as db:
        seed_demo_challenge(db)


def _seed_themes(db_sessionmaker):
    with db_sessionmaker() as db:
        seed_themes(db)


def _set_challenge_theme(db_sessionmaker, theme_id):
    with db_sessionmaker() as db:
        challenge = db.execute(select(Challenge)).scalars().one()
        challenge.theme_id = theme_id
        db.commit()


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
    """Map week number -> task id. A task's `position` is its week number (US-11)."""
    with db_sessionmaker() as db:
        tasks = db.execute(select(Task).order_by(Task.position)).scalars()
        return {t.position: t.id for t in tasks}


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


# --- US-2 (FR-A3): the passport is gated on current-student eligibility ----------


def test_passport_403_for_non_current_student(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client, subject="alum@csub.edu", affiliation="alum")

    resp = client.get("/api/passport")
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "not_current_student"


def test_checkin_403_for_non_current_student(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    _sign_in(client, subject="alum@csub.edu", affiliation="alum")

    resp = client.post("/api/checkins", json={"weekNo": 1})
    assert resp.status_code == 403
    # The gate runs before the service, so nothing is recorded.
    with db_sessionmaker() as db:
        assert list(db.execute(select(CheckIn)).scalars()) == []


# --- Draft challenges stay invisible to students (US-11 authoring) ---------------


def test_passport_404_when_challenge_is_still_draft(client, db_sessionmaker):
    _seed_challenge(db_sessionmaker)
    with db_sessionmaker() as db:
        challenge = db.execute(select(Challenge)).scalars().one()
        challenge.status = "draft"
        db.commit()
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
        "themeConfig",
        "totalWeeks",
        "completedWeeks",
        "remainingWeeks",
        "requiredTotal",
        "requiredCompleted",
        "prizeEligible",
        "weeks",
    }
    assert body["challengeName"] == "Stranger Things Wellness Challenge"
    assert body["theme"] == "stranger-things"

    week1 = body["weeks"][0]
    # Schema now includes taskId and dates may be None if not set
    assert week1["weekNo"] == 1
    assert week1["title"] == "Immunity Portal"
    assert week1["caption"] == (
        "Step through the first portal — survival starts with protection. "
        "Grab your flu shot and wellness kit."
    )
    assert week1["activityType"] == "Flu shot / wellness kit"
    assert week1["location"] == "SHS Lawn"
    assert week1["prize"] == "Wellness kit"
    assert week1["required"] == False
    assert week1["status"] == "available"
    # taskId added for frontend use
    assert "taskId" in week1


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


# --- US-13 (FR-B4 / NFR-6): the passport carries the resolved theme -------------


def test_passport_carries_resolved_theme_config(client, db_sessionmaker):
    """Scenario 1: the student app gets the selected theme's palette, art and copy."""
    _seed_themes(db_sessionmaker)
    _seed_challenge(db_sessionmaker)  # demo challenge uses "stranger-things"
    _sign_in(client)

    body = client.get("/api/passport").json()
    assert body["theme"] == "stranger-things"
    cfg = body["themeConfig"]
    assert cfg["id"] == "stranger-things"
    assert cfg["palette"]["primary"] == "#ff4438"
    assert cfg["palette"]["hero-a"] == "#4a0f0a"
    assert cfg["appTitle"] == "Wellness Passport"
    assert cfg["tagline"] == (
        "Step through the first portal — survival starts with protection."
    )
    assert cfg["copyTone"] == "dark, retro-80s, ominous"


def test_switching_theme_re_skins_from_config_alone(client, db_sessionmaker):
    """Scenario 2: swapping a published challenge's theme changes what the app renders."""
    _seed_themes(db_sessionmaker)
    _seed_challenge(db_sessionmaker)
    _sign_in(client)

    before = client.get("/api/passport").json()["themeConfig"]
    assert before["palette"]["primary"] == "#ff4438"

    _set_challenge_theme(db_sessionmaker, "harry-potter")

    after = client.get("/api/passport").json()["themeConfig"]
    assert after["id"] == "harry-potter"
    assert after["palette"]["primary"] == "#7d2e2e"
    assert after["palette"]["font-display"] == '"Cinzel", Georgia, serif'
    assert after["tagline"] == "Solemnly swear to look after your wellbeing."


def test_edited_theme_is_reflected_in_passport(client, db_sessionmaker):
    """Scenario 3: an admin's palette/copy edit shows up on the student's next fetch."""
    _seed_themes(db_sessionmaker)
    _seed_challenge(db_sessionmaker)
    _sign_in(client)

    assert client.get("/api/passport").json()["themeConfig"]["palette"]["primary"] == (
        "#ff4438"
    )

    with db_sessionmaker() as db:
        theme = db.get(Theme, "stranger-things")
        theme.palette = {**theme.palette, "primary": "#00e5ff"}
        theme.tagline = "The gate is open."
        db.commit()

    cfg = client.get("/api/passport").json()["themeConfig"]
    assert cfg["palette"]["primary"] == "#00e5ff"
    assert cfg["tagline"] == "The gate is open."


def test_checkin_response_carries_theme_config(client, db_sessionmaker):
    """The refreshed passport is themed too, so a check-in never drops the skin."""
    _seed_themes(db_sessionmaker)
    _seed_challenge(db_sessionmaker)
    _sign_in(client)

    body = client.post("/api/checkins", json={"weekNo": 1}).json()
    assert body["themeConfig"]["id"] == "stranger-things"


def test_passport_theme_config_null_for_default_theme(client, db_sessionmaker):
    _seed_themes(db_sessionmaker)
    _seed_challenge(db_sessionmaker)
    _set_challenge_theme(db_sessionmaker, "")
    _sign_in(client)

    body = client.get("/api/passport").json()
    assert body["theme"] == ""
    assert body["themeConfig"] is None


def test_passport_survives_unknown_theme_id(client, db_sessionmaker):
    """A dangling theme_id degrades to the default skin rather than erroring."""
    _seed_challenge(db_sessionmaker)  # themes deliberately not seeded
    _sign_in(client)

    resp = client.get("/api/passport")
    assert resp.status_code == 200
    body = resp.json()
    # The id still rides along — the app's static token blocks can honour it.
    assert body["theme"] == "stranger-things"
    assert body["themeConfig"] is None
