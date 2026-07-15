"""Edge cases for FR-F1 — Participation & completion funnel report (US-21).

The two Gherkin scenarios themselves are executed by test_participation_report_bdd.py
against tests/features/participation_report.feature. This module covers what the
scenarios leave implicit: which challenge counts as "the active challenge", the
shapes that could divide by zero or vanish from the funnel, campus isolation, and
the auth guards.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.models.challenge import Challenge, CheckIn, Enrollment, Task
from app.models.student import Student

ADMIN = "admin@csub.edu"
STUDENTS = ["s1@csub.edu", "s2@csub.edu", "s3@csub.edu"]
REPORT = "/api/reports/participation"


# ---------------------------------------------------------------------------
# Helpers (mirrors the pattern in test_manual_override.py)
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
    return client.post(
        f"/api/challenges/{cid}/tasks/{tid}/checkins",
        json={"student_subject": subject, "reason": "Attended in person"},
    )


def _setup(client, weeks: int = 3, students: list[str] | None = None):
    """A published challenge with N weeks and enrolled students. Ends as admin."""
    _sign_in_as(client, "staff", ADMIN)
    challenge = _create_challenge(client)
    task_ids = _add_weeks(client, challenge["id"], weeks)
    client.post(f"/api/challenges/{challenge['id']}/publish")
    _enroll(client, STUDENTS if students is None else students)
    return challenge["id"], task_ids


def _counts(report: dict) -> dict[int, int]:
    return {w["week_no"]: w["completed_count"] for w in report["weeks"]}


# ---------------------------------------------------------------------------
# Resolving "the active challenge"
# ---------------------------------------------------------------------------


class TestActiveChallengeResolution:
    def test_no_challenge_at_all_is_404_with_a_friendly_code(self, client):
        _sign_in_as(client, "staff")
        resp = client.get(REPORT)
        assert resp.status_code == 404
        # Same contract the enroll route uses, so one client branch covers both.
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
        _add_weeks(client, older["id"], 1)
        client.post(f"/api/challenges/{older['id']}/publish")

        newer = _create_challenge(client, name="Fall 2025", semester="Fall 2025")
        _add_weeks(client, newer["id"], 2)
        client.post(f"/api/challenges/{newer['id']}/publish")

        report = client.get(REPORT).json()
        assert report["challenge"]["id"] == newer["id"]
        assert report["challenge"]["name"] == "Fall 2025"
        assert len(report["weeks"]) == 2

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
    def test_weeks_nobody_finished_still_appear_as_zero(self, client):
        cid, task_ids = _setup(client, weeks=3)
        _mark(client, cid, task_ids[0], STUDENTS[0])

        report = client.get(REPORT).json()
        # The drop-off to zero is the whole point of the funnel — an inner join
        # would silently delete weeks 2 and 3 from the report.
        assert _counts(report) == {1: 1, 2: 0, 3: 0}

    def test_several_students_on_one_week_are_all_counted(self, client):
        cid, task_ids = _setup(client, weeks=2)
        for subject in STUDENTS:
            _mark(client, cid, task_ids[0], subject)

        assert _counts(client.get(REPORT).json()) == {1: 3, 2: 0}

    def test_one_student_across_weeks_counts_once_per_week(self, client):
        cid, task_ids = _setup(client, weeks=3)
        for tid in task_ids:
            _mark(client, cid, tid, STUDENTS[0])

        assert _counts(client.get(REPORT).json()) == {1: 1, 2: 1, 3: 1}

    def test_enrolled_students_who_never_checked_in_still_count_as_enrolled(
        self, client
    ):
        cid, task_ids = _setup(client, weeks=2)
        _mark(client, cid, task_ids[0], STUDENTS[0])

        report = client.get(REPORT).json()
        # Enrollment and completion are independent facts: three joined, one did
        # the work. That gap *is* the participation story the report tells.
        assert report["total_enrollments"] == 3
        assert _counts(report) == {1: 1, 2: 0}

    def test_a_checkin_without_an_enrollment_is_still_counted(self, client):
        """An admin can mark anyone complete — the funnel counts the completion.

        Manual override (FR-D6) does not check enrollment, so a walk-up who never
        joined can hold a check-in. Completions are per-task facts and enrollments
        are per-challenge ones; the report reflects both rather than reconciling
        them, which is why a week's count can exceed total_enrollments.
        """
        cid, task_ids = _setup(client, weeks=1, students=[])
        _sign_in_as(client, "student", "walkup@csub.edu")  # mints the Student row
        _sign_in_as(client, "staff", ADMIN)
        _mark(client, cid, task_ids[0], "walkup@csub.edu")

        report = client.get(REPORT).json()
        assert report["total_enrollments"] == 0
        assert _counts(report) == {1: 1}

    def test_weeks_are_ordered_by_week_number(self, client):
        cid, task_ids = _setup(client, weeks=3)
        # Reversing the authored order must reorder the funnel with it: the
        # report reads position, not insertion order.
        resp = client.put(
            f"/api/challenges/{cid}/tasks/order",
            json={"task_ids": list(reversed(task_ids))},
        )
        assert resp.status_code == 200, resp.text
        _mark(client, cid, task_ids[0], STUDENTS[0])  # now week 3

        report = client.get(REPORT).json()
        assert [w["week_no"] for w in report["weeks"]] == [1, 2, 3]
        assert [w["title"] for w in report["weeks"]] == ["Week 3", "Week 2", "Week 1"]
        assert _counts(report) == {1: 0, 2: 0, 3: 1}


# ---------------------------------------------------------------------------
# Empty shapes — the ones a percentage could divide by zero on
# ---------------------------------------------------------------------------


class TestEmptyShapes:
    def test_challenge_with_no_weeks_reports_an_empty_funnel(self, client):
        _sign_in_as(client, "staff")
        challenge = _create_challenge(client)
        client.post(f"/api/challenges/{challenge['id']}/publish")
        _enroll(client, STUDENTS[:1])

        report = client.get(REPORT).json()
        assert report["weeks"] == []
        assert report["total_enrollments"] == 1

    def test_challenge_with_no_enrollments_reports_zeroes_not_an_error(self, client):
        _sign_in_as(client, "staff")
        challenge = _create_challenge(client)
        _add_weeks(client, challenge["id"], 2)
        client.post(f"/api/challenges/{challenge['id']}/publish")

        report = client.get(REPORT).json()
        assert report["total_enrollments"] == 0
        assert _counts(report) == {1: 0, 2: 0}


# ---------------------------------------------------------------------------
# Campus isolation
# ---------------------------------------------------------------------------


class TestCampusIsolation:
    def test_another_campus_enrollments_and_checkins_are_excluded(
        self, client, db_sessionmaker
    ):
        cid, task_ids = _setup(client, weeks=2)
        _mark(client, cid, task_ids[0], STUDENTS[0])

        # The mock IdP always resolves to campus_id="csub", so a rival campus's
        # data can only be created directly — this is the only way to prove the
        # counts are scoped rather than global.
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

            db.add_all(
                [
                    Enrollment(student_id=rival_student.id, challenge_id=rival.id),
                    CheckIn(
                        student_id=rival_student.id,
                        task_id=rival_task.id,
                        ts=datetime(2026, 1, 8, tzinfo=timezone.utc),
                        method="event_qr",
                    ),
                ]
            )
            db.commit()

        report = client.get(REPORT).json()
        assert report["challenge"]["id"] == cid
        assert report["total_enrollments"] == 3  # not 4
        assert _counts(report) == {1: 1, 2: 0}


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
