"""Edge cases for FR-F5 — Prize-eligible CSV export (US-26).

The two Gherkin scenarios themselves are executed by test_prize_export_bdd.py
against tests/features/prize_export.feature. This module covers what the scenarios
leave implicit: the file's shape and headers, the challenge shapes that could
export everybody or nobody by accident, what ``eligible_since`` actually measures,
campus isolation, and the auth guards.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models.challenge import Challenge, CheckIn, Task
from app.models.student import Student

ADMIN = "admin@csub.edu"
STUDENTS = ["s1@csub.edu", "s2@csub.edu", "s3@csub.edu"]
EXPORT = "/api/reports/prize-eligible.csv"

EXPECTED_HEADER = [
    "student_id",
    "sso_subject",
    "required_completed",
    "required_total",
    "eligible_since",
]


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


def _add_weeks(client, challenge_id: int, required: int, optional: int = 0):
    """Author N required weeks then M optional ones. Returns (required, optional) ids."""
    required_ids = [
        client.post(
            f"/api/challenges/{challenge_id}/tasks",
            json={"title": f"Week {n}", "required": True},
        ).json()["id"]
        for n in range(1, required + 1)
    ]
    optional_ids = [
        client.post(
            f"/api/challenges/{challenge_id}/tasks",
            json={"title": f"Bonus {n}", "required": False},
        ).json()["id"]
        for n in range(1, optional + 1)
    ]
    return required_ids, optional_ids


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


def _setup(client, required: int = 3, optional: int = 0, students=None):
    """A published challenge with N required (+M optional) weeks. Ends as admin."""
    _sign_in_as(client, "staff", ADMIN)
    challenge = _create_challenge(client)
    required_ids, optional_ids = _add_weeks(client, challenge["id"], required, optional)
    client.post(f"/api/challenges/{challenge['id']}/publish")
    _enroll(client, STUDENTS if students is None else students)
    return challenge["id"], required_ids, optional_ids


def _rows(client) -> list[dict]:
    resp = client.get(EXPORT)
    assert resp.status_code == 200, resp.text
    return list(csv.DictReader(io.StringIO(resp.text)))


def _subjects(client) -> list[str]:
    """Exported subjects, in file order — order is asserted, so keep the list."""
    return [row["sso_subject"] for row in _rows(client)]


def _student_id(db, subject: str) -> int:
    return db.scalar(select(Student.id).where(Student.sso_subject == subject))


def _checkin(db, subject: str, task_id: int, ts: datetime) -> None:
    """Record a completion at an authored time.

    The API stamps "now" on every check-in, so any test asserting *which* check-in
    was measured, or what order two of them fell in, has to write the row directly.
    """
    db.add(
        CheckIn(
            student_id=_student_id(db, subject),
            task_id=task_id,
            ts=ts,
            method="event_qr",
        )
    )


# ---------------------------------------------------------------------------
# The file itself
# ---------------------------------------------------------------------------


class TestFileShape:
    def test_response_is_a_named_csv_attachment(self, client):
        _setup(client, required=1)
        resp = client.get(EXPORT)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        # The semester and id both ride along so an admin can tell two downloads
        # apart without opening them.
        assert (
            resp.headers["content-disposition"]
            == 'attachment; filename="prize-eligible-Fall-2025-1.csv"'
        )

    def test_filename_slugifies_an_admin_authored_semester(self, client):
        _sign_in_as(client, "staff")
        challenge = _create_challenge(client, semester="Fall/Winter 2025 (pilot)")
        _add_weeks(client, challenge["id"], required=1)
        client.post(f"/api/challenges/{challenge['id']}/publish")

        # Semester is free text; nothing but [A-Za-z0-9-] may reach the header.
        expected = f"prize-eligible-Fall-Winter-2025-pilot-{challenge['id']}.csv"
        assert (
            client.get(EXPORT).headers["content-disposition"]
            == f'attachment; filename="{expected}"'
        )

    def test_nobody_eligible_is_a_header_only_file_not_an_error(self, client):
        _setup(client, required=2)  # enrolled, but nobody has done anything

        resp = client.get(EXPORT)
        assert resp.status_code == 200
        rows = list(csv.reader(io.StringIO(resp.text)))
        # A valid, empty drawing list: the admin can see the file is right and the
        # cohort simply isn't there yet.
        assert rows == [EXPECTED_HEADER]

    def test_every_row_carries_the_audit_columns(self, client):
        cid, required_ids, _ = _setup(client, required=2)
        for tid in required_ids:
            _mark(client, cid, tid, STUDENTS[0])

        rows = _rows(client)
        assert len(rows) == 1
        assert list(rows[0]) == EXPECTED_HEADER
        assert rows[0]["sso_subject"] == STUDENTS[0]
        assert rows[0]["required_completed"] == "2"
        assert rows[0]["required_total"] == "2"


# ---------------------------------------------------------------------------
# Challenge shapes that could export everybody or nobody
# ---------------------------------------------------------------------------


class TestEligibilityShapes:
    def test_an_all_optional_challenge_makes_nobody_eligible(self, client):
        cid, _, optional_ids = _setup(client, required=0, optional=2)
        for tid in optional_ids:
            _mark(client, cid, tid, STUDENTS[0])

        # Guarded on purpose (services/passport.py): with no required tasks the
        # "completed them all" test is vacuously true, and a challenge nobody can
        # fail must not hand the whole cohort a prize ticket.
        assert _subjects(client) == []

    def test_challenge_with_no_weeks_at_all_exports_nobody(self, client):
        _sign_in_as(client, "staff")
        challenge = _create_challenge(client)
        client.post(f"/api/challenges/{challenge['id']}/publish")
        _enroll(client, STUDENTS[:1])

        assert _subjects(client) == []

    def test_skipping_an_optional_week_does_not_block_eligibility(self, client):
        cid, required_ids, optional_ids = _setup(client, required=2, optional=1)
        for tid in required_ids:
            _mark(client, cid, tid, STUDENTS[0])
        for tid in required_ids + optional_ids:
            _mark(client, cid, tid, STUDENTS[1])

        # Same rule the student's own passport shows: optional weeks are ignored,
        # so doing one is worth nothing here and skipping one costs nothing.
        assert sorted(_subjects(client)) == sorted(STUDENTS[:2])
        assert {row["required_total"] for row in _rows(client)} == {"2"}

    def test_a_checkin_without_an_enrollment_is_still_exported(self, client):
        """The export derives from completions, exactly like the student's passport.

        Manual override (FR-D6) lets an admin mark a walk-up who never enrolled, and
        that student's passport would show them prize-eligible. Excluding them here
        would mean the drawing list and the passport disagree — so Enrollment is
        deliberately not part of the query.
        """
        cid, required_ids, _ = _setup(client, required=1, students=[])
        _sign_in_as(client, "student", "walkup@csub.edu")  # mints the Student row
        _sign_in_as(client, "staff", ADMIN)
        _mark(client, cid, required_ids[0], "walkup@csub.edu")

        assert _subjects(client) == ["walkup@csub.edu"]

    def test_rows_are_ordered_by_when_each_student_became_eligible(
        self, client, db_sessionmaker
    ):
        _, required_ids, _ = _setup(client, required=1)

        # Qualify them in the reverse of the order their Student rows were minted,
        # so ordering by id rather than by time would flip the file.
        with db_sessionmaker() as db:
            for day, subject in enumerate(reversed(STUDENTS), start=1):
                _checkin(
                    db,
                    subject,
                    required_ids[0],
                    datetime(2025, 9, day, tzinfo=timezone.utc),
                )
            db.commit()

        # Ordered by the moment each student qualified, not by id or insertion —
        # two exports of unchanged data must be byte-identical.
        assert _subjects(client) == list(reversed(STUDENTS))


# ---------------------------------------------------------------------------
# eligible_since
# ---------------------------------------------------------------------------


class TestEligibleSince:
    def test_eligible_since_is_the_last_required_checkin_not_a_later_optional_one(
        self, client, db_sessionmaker
    ):
        _, required_ids, optional_ids = _setup(client, required=2, optional=1)

        with db_sessionmaker() as db:
            _checkin(
                db,
                STUDENTS[0],
                required_ids[0],
                datetime(2025, 9, 1, tzinfo=timezone.utc),
            )
            _checkin(
                db,
                STUDENTS[0],
                required_ids[1],
                datetime(2025, 9, 8, tzinfo=timezone.utc),
            )
            # The bonus week, done three weeks after they already qualified.
            _checkin(
                db,
                STUDENTS[0],
                optional_ids[0],
                datetime(2025, 10, 1, tzinfo=timezone.utc),
            )
            db.commit()

        rows = _rows(client)
        assert len(rows) == 1
        # The prize was earned on the 8th, when the last *required* week landed —
        # the bonus week three weeks later did not change when they qualified.
        assert rows[0]["eligible_since"].startswith("2025-09-08")


# ---------------------------------------------------------------------------
# Resolving "the active challenge"
# ---------------------------------------------------------------------------


class TestActiveChallengeResolution:
    def test_no_challenge_at_all_is_404_with_a_friendly_code(self, client):
        _sign_in_as(client, "staff")
        resp = client.get(EXPORT)
        assert resp.status_code == 404
        # Same contract the participation report and enroll route use, so one
        # client branch covers all three.
        assert resp.json()["detail"]["code"] == "no_active_challenge"

    def test_draft_challenge_is_not_exportable(self, client):
        _sign_in_as(client, "staff")
        challenge = _create_challenge(client)
        _add_weeks(client, challenge["id"], required=2)
        # Never published — there is no drawing to run.
        assert client.get(EXPORT).status_code == 404


# ---------------------------------------------------------------------------
# Campus isolation
# ---------------------------------------------------------------------------


class TestCampusIsolation:
    def test_another_campus_eligible_students_are_excluded(self, client, db_sessionmaker):
        cid, required_ids, _ = _setup(client, required=1)
        _mark(client, cid, required_ids[0], STUDENTS[0])

        # The mock IdP always resolves to campus_id="csub", so a rival campus's
        # data can only be created directly — this is the only way to prove the
        # export is scoped rather than global.
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

            rival_task = Task(
                challenge_id=rival.id, position=1, title="Rival Week 1", required=True
            )
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

        # The rival student completed every required task of *their* challenge and
        # still must not appear on this campus's drawing list.
        assert _subjects(client) == [STUDENTS[0]]


# ---------------------------------------------------------------------------
# Auth guards (the repo-wide pair)
# ---------------------------------------------------------------------------


class TestAuthGuards:
    def test_anonymous_cannot_export_the_prize_list(self, client):
        _setup(client, required=1)
        client.cookies.clear()
        assert client.get(EXPORT).status_code == 401

    def test_student_cannot_export_the_prize_list(self, client):
        _setup(client, required=1)
        _sign_in_as(client, "student", STUDENTS[0])
        assert client.get(EXPORT).status_code == 403
