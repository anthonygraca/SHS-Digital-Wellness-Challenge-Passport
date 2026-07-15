"""Edge cases for FR-F2 — Auto-vs-manual attendance report (US-22).

The two Gherkin scenarios themselves are executed by test_attendance_report_bdd.py
against tests/features/attendance_report.feature. This module covers what the
scenarios leave implicit: which challenge counts as "the active challenge", the
counting grain that separates this report from the funnel, the shapes a percentage
could divide by zero on, campus isolation, and the auth guards.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.models.challenge import Challenge, CheckIn, Task
from app.models.student import Student
from app.services.qr import mint_event_token

ADMIN = "admin@csub.edu"
STUDENTS = ["s1@csub.edu", "s2@csub.edu", "s3@csub.edu"]
REPORT = "/api/reports/attendance"


# ---------------------------------------------------------------------------
# Helpers (mirrors the pattern in test_participation_report.py)
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str = ADMIN) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _create_challenge(client, name="Fall 2025 Wellness", semester="Fall 2025", **over):
    payload = {
        "name": name,
        "semester": semester,
        "start_date": "2025-09-01",
        "end_date": "2025-12-15",
        **over,
    }
    return client.post("/api/challenges", json=payload).json()


def _add_weeks(client, challenge_id: int, count: int) -> list[int]:
    return [
        client.post(
            f"/api/challenges/{challenge_id}/tasks",
            json={"title": f"Week {n}", "required": True},
        ).json()["id"]
        for n in range(1, count + 1)
    ]


def _enroll(client, subjects: list[str]) -> None:
    """Enroll each student in the active challenge, then restore the admin session."""
    for subject in subjects:
        _sign_in_as(client, "student", subject)
        client.post("/enrollment")
    _sign_in_as(client, "staff", ADMIN)


def _mark(client, cid: int, tid: int, subject: str):
    """Record a *manual* check-in — the admin override path (FR-D6)."""
    return client.post(
        f"/api/challenges/{cid}/tasks/{tid}/checkins",
        json={"student_subject": subject, "reason": "Attended in person"},
    )


def _scan(client, tid: int, subject: str):
    """Record an *event_qr* check-in as the student, then restore the admin session."""
    _sign_in_as(client, "student", subject)
    resp = client.post("/api/checkins/scan", json={"token": mint_event_token(tid)})
    _sign_in_as(client, "staff", ADMIN)
    return resp


def _setup(client, weeks: int = 3, students: list[str] | None = None):
    """A published challenge with N weeks and enrolled students. Ends as admin."""
    _sign_in_as(client, "staff", ADMIN)
    challenge = _create_challenge(client)
    task_ids = _add_weeks(client, challenge["id"], weeks)
    client.post(f"/api/challenges/{challenge['id']}/publish")
    _enroll(client, STUDENTS if students is None else students)
    return challenge["id"], task_ids


def _counts(report: dict) -> dict[str, int]:
    return {m["method"]: m["count"] for m in report["methods"]}


# ---------------------------------------------------------------------------
# Resolving "the active challenge"
# ---------------------------------------------------------------------------


class TestActiveChallengeResolution:
    def test_no_challenge_at_all_is_404_with_a_friendly_code(self, client):
        _sign_in_as(client, "staff")
        resp = client.get(REPORT)
        assert resp.status_code == 404
        # Same contract /participation and the enroll route use, so one client
        # branch covers all three — and both report cards 404 together.
        assert resp.json()["detail"]["code"] == "no_active_challenge"

    def test_draft_challenge_is_not_reportable(self, client):
        _sign_in_as(client, "staff")
        challenge = _create_challenge(client)
        _add_weeks(client, challenge["id"], 2)
        # Never published — there is nothing running to report on.
        assert client.get(REPORT).status_code == 404

    def test_reports_the_most_recently_starting_published_challenge(self, client):
        _sign_in_as(client, "staff")
        older = _create_challenge(client, name="Spring 2025", semester="Spring 2025")
        older_tasks = _add_weeks(client, older["id"], 1)
        client.post(f"/api/challenges/{older['id']}/publish")
        _enroll(client, STUDENTS[:1])
        _mark(client, older["id"], older_tasks[0], STUDENTS[0])

        newer = _create_challenge(client, name="Fall 2025", semester="Fall 2025")
        _add_weeks(client, newer["id"], 2)
        client.post(f"/api/challenges/{newer['id']}/publish")

        report = client.get(REPORT).json()
        assert report["challenge"]["id"] == newer["id"]
        # The older challenge's check-in belongs to the older challenge — the join
        # through Task is what keeps it out of the current report's counts.
        assert report["total_checkins"] == 0

    def test_report_header_carries_the_challenge_identity(self, client):
        _sign_in_as(client, "staff")
        challenge = _create_challenge(client, theme_id="stranger-things")
        client.post(f"/api/challenges/{challenge['id']}/publish")

        assert client.get(REPORT).json()["challenge"] == {
            "id": challenge["id"],
            "name": "Fall 2025 Wellness",
            "semester": "Fall 2025",
            "theme_id": "stranger-things",
        }


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


class TestCounting:
    def test_checkins_are_counted_not_students(self, client):
        cid, task_ids = _setup(client, weeks=3)
        for tid in task_ids:
            _mark(client, cid, tid, STUDENTS[0])

        report = client.get(REPORT).json()
        # One student, three weeks. The funnel's count(distinct student_id) would
        # say 1; this report counts *captures*, and three is the effort figure.
        assert _counts(report) == {"event_qr": 0, "staff": 0, "manual": 3}
        assert report["total_checkins"] == 3

    def test_qr_and_manual_land_in_different_buckets(self, client):
        cid, task_ids = _setup(client, weeks=3)
        _scan(client, task_ids[0], STUDENTS[0])
        _scan(client, task_ids[1], STUDENTS[0])
        _mark(client, cid, task_ids[2], STUDENTS[1])

        report = client.get(REPORT).json()
        assert _counts(report) == {"event_qr": 2, "staff": 0, "manual": 1}
        assert report["total_checkins"] == 3

    def test_a_staff_checkin_lands_in_the_staff_bucket(self, client, db_sessionmaker):
        """The staff bucket is real, not a hard-coded zero.

        No write path mints method="staff" today, so the row can only be created
        directly — the same reason test_participation_report.py reaches past the API
        for its rival-campus fixture. Without this, a service that always reported
        staff: 0 would pass every other test in this file.
        """
        _, task_ids = _setup(client, weeks=2, students=[])
        with db_sessionmaker() as db:
            student = Student(
                campus_id="csub", sso_subject="walkup@csub.edu", affiliation="student"
            )
            db.add(student)
            db.flush()
            db.add(CheckIn(student_id=student.id, task_id=task_ids[0], method="staff"))
            db.commit()

        report = client.get(REPORT).json()
        assert _counts(report) == {"event_qr": 0, "staff": 1, "manual": 0}
        assert report["total_checkins"] == 1

    def test_an_unrecognized_method_shows_as_a_gap_not_a_silent_drop(
        self, client, db_sessionmaker
    ):
        """A method outside CheckInMethod widens the total without filling a bucket.

        Makes the service's total_checkins comment executable: the total is counted
        across every row, so a write-path bug that minted an unknown method surfaces
        as buckets that no longer reconcile, rather than vanishing from the report.
        """
        cid, task_ids = _setup(client, weeks=2)
        _mark(client, cid, task_ids[0], STUDENTS[0])
        with db_sessionmaker() as db:
            student = db.query(Student).filter_by(sso_subject=STUDENTS[1]).one()
            db.add(
                CheckIn(
                    student_id=student.id, task_id=task_ids[0], method="legacy_import"
                )
            )
            db.commit()

        report = client.get(REPORT).json()
        assert _counts(report) == {"event_qr": 0, "staff": 0, "manual": 1}
        assert report["total_checkins"] == 2
        assert sum(_counts(report).values()) < report["total_checkins"]

    def test_buckets_reconcile_with_the_total_for_real_data(self, client):
        cid, task_ids = _setup(client, weeks=3)
        _scan(client, task_ids[0], STUDENTS[0])
        _scan(client, task_ids[0], STUDENTS[1])
        _mark(client, cid, task_ids[1], STUDENTS[0])

        report = client.get(REPORT).json()
        assert sum(_counts(report).values()) == report["total_checkins"] == 3


# ---------------------------------------------------------------------------
# Empty shapes — the ones a percentage could divide by zero on
# ---------------------------------------------------------------------------


class TestEmptyShapes:
    def test_challenge_with_no_checkins_reports_zeroes_not_an_error(self, client):
        _setup(client, weeks=2)

        report = client.get(REPORT).json()
        # All three buckets present at zero, and the denominator the card must
        # guard against dividing by.
        assert _counts(report) == {"event_qr": 0, "staff": 0, "manual": 0}
        assert report["total_checkins"] == 0

    def test_challenge_with_no_weeks_reports_zeroes(self, client):
        _sign_in_as(client, "staff")
        challenge = _create_challenge(client)
        client.post(f"/api/challenges/{challenge['id']}/publish")

        report = client.get(REPORT).json()
        # No tasks means nothing for a check-in to hang off, so the join finds
        # nothing — but the buckets still ship.
        assert _counts(report) == {"event_qr": 0, "staff": 0, "manual": 0}
        assert report["total_checkins"] == 0

    def test_methods_always_arrive_in_a_fixed_order(self, client):
        _setup(client, weeks=1)
        report = client.get(REPORT).json()
        # Automatic first — the client renders the rows in the order it receives
        # them, and the auto share is the number the card leads with.
        assert [m["method"] for m in report["methods"]] == [
            "event_qr",
            "staff",
            "manual",
        ]


# ---------------------------------------------------------------------------
# Campus isolation
# ---------------------------------------------------------------------------


class TestCampusIsolation:
    def test_another_campus_checkins_are_excluded(self, client, db_sessionmaker):
        cid, task_ids = _setup(client, weeks=2)
        _mark(client, cid, task_ids[0], STUDENTS[0])

        # The mock IdP always resolves to campus_id="csub", so a rival campus's
        # data can only be created directly — this is the only way to prove the
        # join through Task scopes the counts rather than counting globally.
        with db_sessionmaker() as db:
            rival = Challenge(
                campus_id="other",
                name="Rival Challenge",
                semester="Fall 2025",
                start_date=date(2026, 1, 1),  # would win "most recent" if unscoped
                end_date=date(2026, 5, 1),
                status="published",
            )
            db.add(rival)
            db.flush()

            rival_task = Task(challenge_id=rival.id, position=1, title="Rival Week 1")
            rival_student = Student(
                campus_id="other", sso_subject="rival@other.edu", affiliation="student"
            )
            db.add_all([rival_task, rival_student])
            db.flush()

            db.add(
                CheckIn(
                    student_id=rival_student.id,
                    task_id=rival_task.id,
                    ts=datetime(2026, 1, 8, tzinfo=timezone.utc),
                    method="event_qr",
                )
            )
            db.commit()

        report = client.get(REPORT).json()
        assert report["challenge"]["id"] == cid
        # The rival's event_qr scan must not inflate this campus's auto share.
        assert _counts(report) == {"event_qr": 0, "staff": 0, "manual": 1}
        assert report["total_checkins"] == 1


# ---------------------------------------------------------------------------
# Auth guards (the repo-wide pair)
# ---------------------------------------------------------------------------


class TestAuthGuards:
    def test_anonymous_cannot_read_the_report(self, client):
        _setup(client, weeks=1)
        client.cookies.clear()
        assert client.get(REPORT).status_code == 401

    def test_student_cannot_read_the_report(self, client):
        _setup(client, weeks=1)
        _sign_in_as(client, "student", STUDENTS[0])
        assert client.get(REPORT).status_code == 403
