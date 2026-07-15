"""Edge cases for FR-F4 — Learning-outcome aggregate report (US-24).

The two Gherkin scenarios themselves are executed by test_learning_outcome_report_bdd.py
against tests/features/learning_outcome_report.feature. This module covers what the
scenarios leave implicit: which challenge a report answers for and who may ask for one,
the tag whose items nobody has answered, the weighting the total mean uses, the
structural zero the human bucket reports until US-19, the shapes an empty challenge
takes, and campus isolation.

Mirrors the pattern in test_engagement_report.py rather than importing from it — each
report's helpers stay readable next to the report they exercise.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.challenge import (
    AssessmentItem,
    AssessmentResponse,
    Challenge,
    Task,
)
from app.models.student import Student

ADMIN = "admin@csub.edu"
STUDENTS = ["s1@csub.edu", "s2@csub.edu", "s3@csub.edu"]
REPORT = "/api/reports/outcomes"

CORRECT = "Every 1-2 years"
INCORRECT = "Once, when I turn 18"
OPTIONS = [CORRECT, INCORRECT, "Only when my vision seems blurry", "Every 5 years"]

TAG_A = "know-your-numbers"
TAG_B = "stress-management"


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


def _add_mcq(client, challenge_id: int, task_id: int, outcome_tag: str) -> int:
    resp = client.post(
        f"/api/challenges/{challenge_id}/tasks/{task_id}/items",
        json={
            "item_type": "mcq",
            "prompt": f"An MCQ tagged {outcome_tag}?",
            "outcome_tag": outcome_tag,
            "options": OPTIONS,
            "answer_key": CORRECT,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _add_reflection(client, challenge_id: int, task_id: int, outcome_tag: str) -> int:
    resp = client.post(
        f"/api/challenges/{challenge_id}/tasks/{task_id}/items",
        json={
            "item_type": "reflection",
            "prompt": f"Reflect on {outcome_tag}.",
            "outcome_tag": outcome_tag,
            "rubric": "Mentions at least two habits.",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _answer(client, item_id: int, subject: str, answer: str):
    """Answer an MCQ as the student, then restore the admin session."""
    _sign_in_as(client, "student", subject)
    resp = client.post(
        f"/api/assessments/items/{item_id}/responses", json={"answer": answer}
    )
    _sign_in_as(client, "staff", ADMIN)
    return resp


def _mint_student(client, subject: str) -> None:
    """Sign a student in once, which is what creates their Student row.

    Needed before hand-writing a response for someone who never answered an MCQ —
    a reflection author has signed in, so the row exists in reality too.
    """
    _sign_in_as(client, "student", subject)
    _sign_in_as(client, "staff", ADMIN)


def _override(db_sessionmaker, item_id: int, subject: str, score: float) -> None:
    """Hand-write a scored_by="human" row — US-19's write path, until it exists."""
    with db_sessionmaker() as db:
        student = db.query(Student).filter_by(sso_subject=subject).one()
        db.add(
            AssessmentResponse(
                student_id=student.id,
                assessment_item_id=item_id,
                response="An essay.",
                score=score,
                scored_by="human",
            )
        )
        db.commit()


def _setup(client, weeks: int = 2):
    """A published challenge with an MCQ on week 1 and another on week 2. Ends as admin.

    No enrollment: this report does not consult it, for the reason
    prize_eligible_students gives — a student with responses but no enrollment row
    must not read differently here than their own score does to them.
    """
    _sign_in_as(client, "staff", ADMIN)
    challenge = _create_challenge(client)
    task_ids = _add_weeks(client, challenge["id"], weeks)
    items = [
        _add_mcq(client, challenge["id"], task_ids[0], TAG_A),
        _add_mcq(client, challenge["id"], task_ids[1], TAG_B),
    ]
    client.post(f"/api/challenges/{challenge['id']}/publish")
    return challenge["id"], task_ids, items


def _by_tag(report: dict) -> dict[str, dict]:
    return {o["outcome_tag"]: o for o in report["outcomes"]}


class TestChallengeResolution:
    def test_no_challenge_at_all_is_a_structured_404(self, client):
        _sign_in_as(client, "staff", ADMIN)
        resp = client.get(REPORT)
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "no_active_challenge"

    def test_a_draft_challenge_is_not_reportable(self, client):
        _sign_in_as(client, "staff", ADMIN)
        challenge = _create_challenge(client)
        _add_weeks(client, challenge["id"], 1)
        # Never published — an admin still authoring a challenge has nothing to report.
        assert client.get(REPORT).status_code == 404

    def test_a_draft_cannot_be_reached_by_asking_for_it_by_id(self, client):
        """The challenge_id parameter selects, it does not unlock."""
        _sign_in_as(client, "staff", ADMIN)
        published, _, _ = _setup(client)
        draft = _create_challenge(client, name="Spring 2026", semester="Spring 2026")

        assert client.get(REPORT, params={"challenge_id": draft["id"]}).status_code == 404
        assert client.get(REPORT, params={"challenge_id": published}).status_code == 200

    def test_a_prior_semester_is_reportable_by_id(self, client):
        """Comparing this semester's outcomes against last is the reason to keep them.

        US-24's Gherkin never asks for the parameter; the route takes it anyway, and a
        per-outcome mean is the number most worth reading across semesters.
        """
        _sign_in_as(client, "staff", ADMIN)
        older = _create_challenge(
            client, name="Spring 2025", semester="Spring 2025", start_date="2025-01-15"
        )
        older_tasks = _add_weeks(client, older["id"], 1)
        older_item = _add_mcq(client, older["id"], older_tasks[0], TAG_A)
        client.post(f"/api/challenges/{older['id']}/publish")
        _answer(client, older_item, STUDENTS[0], CORRECT)

        # A newer published challenge takes over as the active one.
        _setup(client)

        report = client.get(REPORT, params={"challenge_id": older["id"]}).json()
        assert report["challenge"]["semester"] == "Spring 2025"
        assert report["total_responses"] == 1
        assert _by_tag(report)[TAG_A]["mean_score"] == pytest.approx(1.0)

        # The active report, by contrast, has no responses at all.
        assert client.get(REPORT).json()["total_responses"] == 0


class TestAggregation:
    def test_scores_group_by_tag_not_by_item(self, client):
        """Two items sharing a tag are one bucket — the tag is the unit, not the question.

        Without this, "aggregated by learning outcome" would silently mean "per
        question", and an outcome assessed twice would report twice.
        """
        _sign_in_as(client, "staff", ADMIN)
        challenge = _create_challenge(client)
        tasks = _add_weeks(client, challenge["id"], 2)
        first = _add_mcq(client, challenge["id"], tasks[0], TAG_A)
        second = _add_mcq(client, challenge["id"], tasks[1], TAG_A)
        client.post(f"/api/challenges/{challenge['id']}/publish")

        _answer(client, first, STUDENTS[0], CORRECT)
        _answer(client, second, STUDENTS[0], INCORRECT)

        report = client.get(REPORT).json()
        assert len(report["outcomes"]) == 1
        assert report["outcomes"][0]["outcome_tag"] == TAG_A
        assert report["outcomes"][0]["response_count"] == 2
        assert report["outcomes"][0]["mean_score"] == pytest.approx(0.5)

    def test_the_total_mean_is_weighted_by_response_not_by_tag(self, client):
        """The mean of every score, never the mean of the per-tag means.

        TAG_A: 3 responses, all correct -> 1.0. TAG_B: 1 response, wrong -> 0.0.
        Weighted, the cohort scored 3/4 = 0.75. Averaging the two tag means gives
        0.5 — which would let one response outvote three, and is a different answer
        to "how did the cohort do" than the one FR-F4 asks for.
        """
        _, _, items = _setup(client)
        for subject in STUDENTS:
            _answer(client, items[0], subject, CORRECT)
        _answer(client, items[1], STUDENTS[0], INCORRECT)

        report = client.get(REPORT).json()
        assert report["total_responses"] == 4
        assert report["mean_score"] == pytest.approx(0.75)
        assert report["mean_score"] != pytest.approx(0.5)

    def test_tags_arrive_alphabetically_whatever_order_they_were_authored_in(
        self, client
    ):
        """Deterministic order, so a refreshed card does not reshuffle under an admin.

        Authored zebra-first; the report must still lead with alpha. Ordering by score
        would also have passed a same-order check by luck, so the scores are set to
        put the tags in the opposite order to their names.
        """
        _sign_in_as(client, "staff", ADMIN)
        challenge = _create_challenge(client)
        tasks = _add_weeks(client, challenge["id"], 2)
        zebra = _add_mcq(client, challenge["id"], tasks[0], "zebra-outcome")
        alpha = _add_mcq(client, challenge["id"], tasks[1], "alpha-outcome")
        client.post(f"/api/challenges/{challenge['id']}/publish")

        _answer(client, zebra, STUDENTS[0], CORRECT)  # 1.0
        _answer(client, alpha, STUDENTS[0], INCORRECT)  # 0.0

        report = client.get(REPORT).json()
        assert [o["outcome_tag"] for o in report["outcomes"]] == [
            "alpha-outcome",
            "zebra-outcome",
        ]

    def test_one_attempt_per_item_keeps_the_mean_from_drifting_to_one(self, client):
        """uq_response_student_item is what stops a wrong answer being re-answered right.

        The FR-E4 feedback names the correct option, so without the constraint every
        stored score would climb to 1.0 and this report would be a flat line. Asserted
        here as well as in test_mcq_scoring.py: that test owns the 409, this one owns
        what the 409 protects.
        """
        _, _, items = _setup(client)
        _answer(client, items[0], STUDENTS[0], INCORRECT)
        retry = _answer(client, items[0], STUDENTS[0], CORRECT)

        assert retry.status_code == 409
        report = client.get(REPORT).json()
        assert _by_tag(report)[TAG_A]["mean_score"] == pytest.approx(0.0)
        assert _by_tag(report)[TAG_A]["response_count"] == 1


class TestUnansweredTags:
    def test_a_tag_nobody_has_answered_is_still_a_row(self, client):
        """The outer join, and the whole reason the query starts from the items.

        "Nobody has answered anything tagged stress-management" is a finding — it is
        what tells an admin the assessment is not landing — and a report that emitted
        only the answered tags would make it indistinguishable from a tag that does
        not exist. The other reports get this guarantee by seeding their buckets from
        a constant; an outcome tag is admin-authored, so the items are the only place
        the vocabulary can be read from.
        """
        _, _, items = _setup(client)
        _answer(client, items[0], STUDENTS[0], CORRECT)

        outcomes = _by_tag(client.get(REPORT).json())
        assert set(outcomes) == {TAG_A, TAG_B}
        assert outcomes[TAG_B]["response_count"] == 0
        assert outcomes[TAG_B]["human_scored_count"] == 0

    def test_an_unanswered_tag_has_no_mean_rather_than_a_mean_of_zero(self, client):
        """None, not 0.0 — the difference between "no data" and "everybody failed".

        0.0 would render as a 0% bar an admin would read as a catastrophe, when the
        truth is that the question has not been asked yet.
        """
        _, _, items = _setup(client)
        _answer(client, items[0], STUDENTS[0], CORRECT)

        assert _by_tag(client.get(REPORT).json())[TAG_B]["mean_score"] is None

    def test_a_tag_everybody_got_wrong_scores_zero_not_none(self, client):
        """The other side of the line above: 0.0 is a real mean and must survive.

        A report that used None for "no score" and also let a 0.0 mean fall through to
        None would erase exactly the outcome most worth acting on.
        """
        _, _, items = _setup(client)
        _answer(client, items[0], STUDENTS[0], INCORRECT)
        _answer(client, items[0], STUDENTS[1], INCORRECT)

        outcomes = _by_tag(client.get(REPORT).json())
        assert outcomes[TAG_A]["mean_score"] == pytest.approx(0.0)
        assert outcomes[TAG_A]["mean_score"] is not None
        assert outcomes[TAG_A]["response_count"] == 2


class TestHumanScored:
    def test_the_human_bucket_is_a_structural_zero_today(self, client):
        """Reported, not omitted — the zero says the US-19 override path is not wired.

        Same claim AttendanceReportOut makes with `staff: 0`. Every response the app
        can currently write is auto-scored, and an admin should be able to read that
        off the report rather than infer it from a missing field.
        """
        _, _, items = _setup(client)
        for subject in STUDENTS:
            _answer(client, items[0], subject, CORRECT)

        report = client.get(REPORT).json()
        assert report["total_human_scored"] == 0
        assert all(o["human_scored_count"] == 0 for o in report["outcomes"])
        # And the responses are all there — the zero is about provenance, not absence.
        assert report["total_responses"] == 3

    def test_a_human_score_is_counted_as_human_and_still_included(
        self, client, db_sessionmaker
    ):
        """Counted separately, filtered never. Both halves matter.

        The separate count is what makes "overridden scores are included" checkable;
        the inclusion is what FR-F4 asks for. A report that only did the first would
        report a human score it had excluded from its own mean.
        """
        challenge_id, tasks, items = _setup(client)
        _sign_in_as(client, "staff", ADMIN)
        reflection = _add_reflection(client, challenge_id, tasks[0], TAG_A)

        _answer(client, items[0], STUDENTS[0], INCORRECT)  # 0.0, auto
        _override(db_sessionmaker, reflection, STUDENTS[0], 1.0)  # 1.0, human

        outcomes = _by_tag(client.get(REPORT).json())
        assert outcomes[TAG_A]["response_count"] == 2
        assert outcomes[TAG_A]["human_scored_count"] == 1
        # 0.0 and 1.0 -> 0.5. Excluding the human row would give 0.0; excluding the
        # auto one would give 1.0. Only counting both lands here.
        assert outcomes[TAG_A]["mean_score"] == pytest.approx(0.5)

    def test_a_fractional_rubric_score_survives_the_mean(self, client, db_sessionmaker):
        """AssessmentResponse.score is a Float for this: a rubric score is not 0 or 1.

        An Integer column, or a report that rounded on the way out, would silently
        turn a 0.5 into a 0 or a 1 — and US-19's whole grain would be lost between
        the override and the report that is supposed to show it.
        """
        challenge_id, tasks, _ = _setup(client)
        _sign_in_as(client, "staff", ADMIN)
        reflection = _add_reflection(client, challenge_id, tasks[0], TAG_A)
        _mint_student(client, STUDENTS[0])
        _override(db_sessionmaker, reflection, STUDENTS[0], 0.5)

        outcomes = _by_tag(client.get(REPORT).json())
        assert outcomes[TAG_A]["mean_score"] == pytest.approx(0.5)


class TestEmptyShapes:
    def test_a_challenge_with_no_items_reports_no_outcomes_and_no_mean(self, client):
        """Every field present and honest: an empty list, and None rather than 0.0.

        The card branches on total_responses == 0, so this is the shape it branches on.
        """
        _sign_in_as(client, "staff", ADMIN)
        challenge = _create_challenge(client)
        _add_weeks(client, challenge["id"], 2)
        client.post(f"/api/challenges/{challenge['id']}/publish")

        report = client.get(REPORT).json()
        assert report["outcomes"] == []
        assert report["total_responses"] == 0
        assert report["mean_score"] is None
        assert report["total_human_scored"] == 0

    def test_items_but_no_answers_reports_every_tag_at_zero(self, client):
        """Not the same emptiness as above: the tags exist, the answers do not."""
        _setup(client)

        report = client.get(REPORT).json()
        assert [o["outcome_tag"] for o in report["outcomes"]] == [TAG_A, TAG_B]
        assert all(o["response_count"] == 0 for o in report["outcomes"])
        assert all(o["mean_score"] is None for o in report["outcomes"])
        assert report["total_responses"] == 0
        assert report["mean_score"] is None

    def test_the_header_carries_what_the_report_shows(self, client):
        cid, _, _ = _setup(client)
        assert client.get(REPORT).json()["challenge"] == {
            "id": cid,
            "name": "Fall 2025 Wellness",
            "semester": "Fall 2025",
            "theme_id": "",
        }


class TestCampusIsolation:
    def test_another_campus_responses_are_excluded(self, client, db_sessionmaker):
        cid, _, items = _setup(client)
        _answer(client, items[0], STUDENTS[0], CORRECT)

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
            # Shares our tag on purpose: if the join through Task were dropped, their
            # scores would land in our bucket rather than showing up as a new row, so
            # the leak would be invisible in the tag list.
            item = AssessmentItem(
                task_id=task.id,
                item_type="mcq",
                prompt="Rival question?",
                outcome_tag=TAG_A,
                options=OPTIONS,
                answer_key=CORRECT,
            )
            db.add(item)
            db.flush()
            db.add(
                AssessmentResponse(
                    student_id=student.id,
                    assessment_item_id=item.id,
                    response=INCORRECT,
                    score=0.0,
                    scored_by="auto",
                )
            )
            db.commit()
            rival_id = rival.id

        report = client.get(REPORT).json()
        assert report["challenge"]["id"] == cid
        # Their 0.0 would drag our 1.0 to 0.5 if it were counted.
        assert report["total_responses"] == 1
        assert _by_tag(report)[TAG_A]["mean_score"] == pytest.approx(1.0)
        assert _by_tag(report)[TAG_A]["response_count"] == 1

        # And their challenge cannot be reached by naming it: a 404, not a 403, so
        # the report cannot be used to probe which ids exist on other campuses.
        assert client.get(REPORT, params={"challenge_id": rival_id}).status_code == 404


class TestAuthGuards:
    def test_anonymous_is_401(self, client):
        _setup(client)
        client.cookies.clear()
        assert client.get(REPORT).status_code == 401

    def test_student_is_403(self, client):
        """Aggregate or not, cohort scores are not a student's to read (FR-F6)."""
        _setup(client)
        _sign_in_as(client, "student", STUDENTS[0])
        assert client.get(REPORT).status_code == 403
