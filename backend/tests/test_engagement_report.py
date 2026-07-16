"""Edge cases for FR-F3 — Engagement report (US-23).

The Gherkin scenario itself is executed by test_engagement_report_bdd.py against
tests/features/engagement_report.feature. This module covers what the scenario
leaves implicit: which challenge a report answers for and who may ask for one, the
counting grain that separates this report from the funnel, the structural zero the
guide bucket reports until US-16, the shapes an empty challenge takes, campus
isolation, and the write path that puts rows in the table at all.

Mirrors the pattern in test_attendance_report.py rather than importing from it —
each report's helpers stay readable next to the report they exercise.
"""

from __future__ import annotations

from datetime import date

from app.models.challenge import Challenge, Task
from app.models.engagement import ContentView, GuideSession
from app.models.student import Student
from app.services.qr import mint_event_token

ADMIN = "admin@csub.edu"
STUDENTS = ["s1@csub.edu", "s2@csub.edu"]
REPORT = "/api/reports/engagement"
VIEWS = "/api/content-views"


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


def _view(client, week_no: int, subject: str, content_ref: str = "week_detail"):
    """Record a content view as the student, then restore the admin session."""
    _sign_in_as(client, "student", subject)
    resp = client.post(VIEWS, json={"weekNo": week_no, "contentRef": content_ref})
    _sign_in_as(client, "staff", ADMIN)
    return resp


def _scan(client, task_id: int, subject: str):
    """Scan an event QR — the only thing that mints a `tip` view (routers/passport)."""
    _sign_in_as(client, "student", subject)
    resp = client.post("/api/checkins/scan", json={"token": mint_event_token(task_id)})
    _sign_in_as(client, "staff", ADMIN)
    return resp


def _setup(client, weeks: int = 3):
    """A published challenge with N weeks. Ends as admin.

    No enrollment: neither the content-view write path nor this report consults it,
    for the reason prize_eligible_students gives — a student with views but no
    enrollment row must not read differently here than they do to themselves.
    """
    _sign_in_as(client, "staff", ADMIN)
    challenge = _create_challenge(client)
    task_ids = _add_weeks(client, challenge["id"], weeks)
    client.post(f"/api/challenges/{challenge['id']}/publish")
    return challenge["id"], task_ids


def _counts(report: dict) -> dict[str, int]:
    return {v["content_ref"]: v["count"] for v in report["content_views"]}


class TestChallengeResolution:
    def test_no_challenge_at_all_is_a_structured_404(self, client):
        _sign_in_as(client, "staff", ADMIN)
        resp = client.get(REPORT)
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "no_active_challenge"

    def test_a_draft_challenge_is_not_reportable(self, client):
        _sign_in_as(client, "staff", ADMIN)
        challenge = _create_challenge(client)
        _add_weeks(client, challenge["id"], 2)
        # Never published — an admin still authoring a challenge has nothing to report.
        assert client.get(REPORT).status_code == 404

    def test_a_draft_cannot_be_reached_by_asking_for_it_by_id(self, client):
        """The challenge_id parameter selects, it does not unlock.

        Without this the parameter would quietly become the one way to report on a
        draft, and the rule above would hold only for challenges nobody names.
        """
        _sign_in_as(client, "staff", ADMIN)
        published, _ = _setup(client, weeks=1)
        draft = _create_challenge(client, name="Spring 2026", semester="Spring 2026")

        assert client.get(REPORT, params={"challenge_id": draft["id"]}).status_code == 404
        assert client.get(REPORT, params={"challenge_id": published}).status_code == 200

    def test_the_default_report_is_the_most_recently_starting_published_challenge(
        self, client
    ):
        _sign_in_as(client, "staff", ADMIN)
        older = _create_challenge(
            client, name="Spring 2025", semester="Spring 2025", start_date="2025-01-15"
        )
        client.post(f"/api/challenges/{older['id']}/publish")
        newer, _ = _setup(client, weeks=1)

        assert client.get(REPORT).json()["challenge"]["id"] == newer

    def test_a_prior_semester_is_reportable_by_id(self, client):
        """The whole point of the parameter: without it, last semester is unreachable."""
        _sign_in_as(client, "staff", ADMIN)
        older = _create_challenge(
            client, name="Spring 2025", semester="Spring 2025", start_date="2025-01-15"
        )
        client.post(f"/api/challenges/{older['id']}/publish")
        _setup(client, weeks=1)

        report = client.get(REPORT, params={"challenge_id": older["id"]}).json()
        assert report["challenge"]["id"] == older["id"]
        assert report["challenge"]["semester"] == "Spring 2025"

    def test_the_header_carries_what_the_report_shows(self, client):
        cid, _ = _setup(client, weeks=1)
        challenge = client.get(REPORT).json()["challenge"]
        assert challenge == {
            "id": cid,
            "name": "Fall 2025 Wellness",
            "semester": "Fall 2025",
            "theme_id": "",
        }


class TestCounting:
    def test_views_are_counted_not_viewers(self, client):
        _setup(client, weeks=2)
        _view(client, 1, STUDENTS[0])
        _view(client, 1, STUDENTS[0])
        _view(client, 1, STUDENTS[0])

        report = client.get(REPORT).json()
        # One student, one week, three opens. The funnel's count(distinct student_id)
        # would say 1; this report counts *views*, and three is the engagement figure.
        assert _counts(report) == {"week_detail": 3, "tip": 0}
        assert report["total_content_views"] == 3

    def test_week_detail_and_tip_land_in_different_buckets(self, client):
        _, task_ids = _setup(client, weeks=2)
        _view(client, 1, STUDENTS[0])
        _scan(client, task_ids[0], STUDENTS[1])

        report = client.get(REPORT).json()
        assert _counts(report) == {"week_detail": 1, "tip": 1}

    def test_a_scan_writes_its_tip_view_without_the_client_reporting_it(self, client):
        """The scan route delivers the tip, so the scan route records it.

        Nothing but the scan happens here — no POST to /api/content-views. If the
        tip view were the client's job to report, this count would be 0.
        """
        _, task_ids = _setup(client, weeks=1)
        _scan(client, task_ids[0], STUDENTS[0])

        assert _counts(client.get(REPORT).json())["tip"] == 1

    def test_buckets_reconcile_with_the_total_for_real_data(self, client):
        _, task_ids = _setup(client, weeks=3)
        _view(client, 1, STUDENTS[0])
        _view(client, 2, STUDENTS[0])
        _view(client, 1, STUDENTS[1])
        _scan(client, task_ids[0], STUDENTS[0])

        report = client.get(REPORT).json()
        assert sum(_counts(report).values()) == report["total_content_views"] == 4


class TestGuideSessions:
    def test_guide_sessions_are_a_structural_zero_today(self, client):
        """No write path mints a GuideSession until the guide ships (US-16).

        Reported rather than omitted, exactly as the attendance report's `staff`
        bucket is: the zero tells an admin the guide is not wired up yet, which is a
        finding they can read rather than an absence they have to infer.
        """
        _setup(client, weeks=2)
        _view(client, 1, STUDENTS[0])

        assert client.get(REPORT).json()["guide_sessions"] == 0

    def test_a_guide_session_lands_in_the_count(self, client, db_sessionmaker):
        """The guide count is real, not a hard-coded zero.

        No write path mints one today, so the row can only be created directly — the
        same reason test_attendance_report.py reaches past the API for its `staff`
        bucket. Without this, a service that always reported guide_sessions: 0 would
        pass every other test in this file.
        """
        cid, _ = _setup(client, weeks=1)
        with db_sessionmaker() as db:
            student = Student(
                campus_id="csub", sso_subject="chatty@csub.edu", affiliation="student"
            )
            db.add(student)
            db.flush()
            db.add(GuideSession(student_id=student.id, challenge_id=cid))
            db.add(GuideSession(student_id=student.id, challenge_id=cid))
            db.commit()

        assert client.get(REPORT).json()["guide_sessions"] == 2

    def test_guide_sessions_do_not_leak_across_challenges(self, client, db_sessionmaker):
        _sign_in_as(client, "staff", ADMIN)
        older = _create_challenge(
            client, name="Spring 2025", semester="Spring 2025", start_date="2025-01-15"
        )
        client.post(f"/api/challenges/{older['id']}/publish")
        active, _ = _setup(client, weeks=1)

        with db_sessionmaker() as db:
            student = Student(
                campus_id="csub", sso_subject="chatty@csub.edu", affiliation="student"
            )
            db.add(student)
            db.flush()
            db.add(GuideSession(student_id=student.id, challenge_id=older["id"]))
            db.commit()

        assert client.get(REPORT).json()["guide_sessions"] == 0
        prior = client.get(REPORT, params={"challenge_id": older["id"]}).json()
        assert prior["guide_sessions"] == 1
        assert active == client.get(REPORT).json()["challenge"]["id"]


class TestEmptyShapes:
    def test_a_challenge_with_no_views_is_all_zeroes(self, client):
        _setup(client, weeks=3)
        report = client.get(REPORT).json()
        assert _counts(report) == {"week_detail": 0, "tip": 0}
        assert report["total_content_views"] == 0
        assert report["guide_sessions"] == 0

    def test_a_challenge_with_no_weeks_is_all_zeroes(self, client):
        _sign_in_as(client, "staff", ADMIN)
        challenge = _create_challenge(client)
        client.post(f"/api/challenges/{challenge['id']}/publish")

        report = client.get(REPORT).json()
        assert report["total_content_views"] == 0
        assert _counts(report) == {"week_detail": 0, "tip": 0}

    def test_content_refs_always_arrive_in_a_fixed_order(self, client):
        _setup(client, weeks=1)
        report = client.get(REPORT).json()
        # Week detail first — the view a student chooses to make. The client renders
        # the rows in the order it receives them.
        assert [v["content_ref"] for v in report["content_views"]] == [
            "week_detail",
            "tip",
        ]

    def test_an_unrecognized_content_ref_shows_as_a_gap_not_a_silent_drop(
        self, client, db_sessionmaker
    ):
        """A ref outside ContentRef widens the total without filling a bucket.

        Makes the service's total_content_views comment executable: the total is
        counted across every row, so a write-path bug that minted an unknown ref
        surfaces as buckets that no longer reconcile, rather than vanishing.
        """
        _, task_ids = _setup(client, weeks=2)
        _view(client, 1, STUDENTS[0])
        with db_sessionmaker() as db:
            student = db.query(Student).filter_by(sso_subject=STUDENTS[0]).one()
            db.add(
                ContentView(
                    student_id=student.id, task_id=task_ids[0], content_ref="video"
                )
            )
            db.commit()

        report = client.get(REPORT).json()
        assert _counts(report) == {"week_detail": 1, "tip": 0}
        assert report["total_content_views"] == 2
        assert sum(_counts(report).values()) < report["total_content_views"]


class TestCampusIsolation:
    def test_another_campus_views_are_excluded(self, client, db_sessionmaker):
        cid, _ = _setup(client, weeks=2)
        _view(client, 1, STUDENTS[0])

        with db_sessionmaker() as db:
            # Starts later than ours, so it would win "most recent" if the campus
            # filter were dropped.
            rival = Challenge(
                campus_id="other",
                name="Rival",
                semester="Spring 2026",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 5, 1),
                status="published",
            )
            db.add(rival)
            db.flush()
            task = Task(challenge_id=rival.id, position=1, title="Rival week")
            student = Student(
                campus_id="other", sso_subject="rival@other.edu", affiliation="student"
            )
            db.add_all([task, student])
            db.flush()
            db.add(
                ContentView(
                    student_id=student.id, task_id=task.id, content_ref="week_detail"
                )
            )
            db.add(GuideSession(student_id=student.id, challenge_id=rival.id))
            db.commit()
            rival_id = rival.id

        report = client.get(REPORT).json()
        assert report["challenge"]["id"] == cid
        assert report["total_content_views"] == 1
        assert report["guide_sessions"] == 0

        # And their challenge cannot be reached by naming it: a 404, not a 403, so
        # the report cannot be used to probe which ids exist on other campuses.
        assert client.get(REPORT, params={"challenge_id": rival_id}).status_code == 404


class TestAuthGuards:
    def test_anonymous_is_401(self, client):
        _setup(client, weeks=1)
        client.cookies.clear()
        assert client.get(REPORT).status_code == 401

    def test_student_is_403(self, client):
        _setup(client, weeks=1)
        _sign_in_as(client, "student", STUDENTS[0])
        assert client.get(REPORT).status_code == 403


class TestContentViewWritePath:
    """The endpoint that puts rows in the table (US-23 instrumentation).

    Its whole job is to increment a number an admin later reads as a fact, so the
    guards matter more than a 204 suggests.
    """

    def test_a_view_is_recorded(self, client):
        _setup(client, weeks=2)
        assert _view(client, 1, STUDENTS[0]).status_code == 204
        assert _counts(client.get(REPORT).json())["week_detail"] == 1

    def test_anonymous_is_401(self, client):
        _setup(client, weeks=1)
        client.cookies.clear()
        resp = client.post(VIEWS, json={"weekNo": 1, "contentRef": "week_detail"})
        assert resp.status_code == 401

    def test_a_non_current_student_is_403(self, client):
        _setup(client, weeks=1)
        _sign_in_as(client, "alum", "grad@csub.edu")
        resp = client.post(VIEWS, json={"weekNo": 1, "contentRef": "week_detail"})
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "not_current_student"

    def test_an_unknown_week_is_404(self, client):
        _setup(client, weeks=2)
        _sign_in_as(client, "student", STUDENTS[0])
        resp = client.post(VIEWS, json={"weekNo": 99, "contentRef": "week_detail"})
        assert resp.status_code == 404

    def test_an_unknown_content_ref_is_rejected(self, client):
        """422 at the edge, so an unbucketable ref never reaches the table."""
        _setup(client, weeks=1)
        _sign_in_as(client, "student", STUDENTS[0])
        resp = client.post(VIEWS, json={"weekNo": 1, "contentRef": "video"})
        assert resp.status_code == 422

    def test_a_view_with_no_active_challenge_is_404(self, client):
        _sign_in_as(client, "staff", ADMIN)
        challenge = _create_challenge(client)
        _add_weeks(client, challenge["id"], 1)
        # Draft only — a student cannot see the passport, so cannot view its content.
        _sign_in_as(client, "student", STUDENTS[0])
        resp = client.post(VIEWS, json={"weekNo": 1, "contentRef": "week_detail"})
        assert resp.status_code == 404
