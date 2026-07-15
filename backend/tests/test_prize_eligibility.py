"""US-7 — Prize-eligibility indicator (FR-C5, source UC-2).

Eligibility is a *derived* query over required-task completion, never a stored flag.
The service-level tests build a challenge with an explicit required/optional mix so
they mirror the story's Gherkin ("4 required tasks") exactly; the API tests exercise
the same rule end-to-end over the seeded 7-week demo challenge (6 required, 1 optional).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.challenge import Challenge, CheckIn, Task
from app.models.student import Student
from app.services.passport import build_passport
from app.services.seed import seed_demo_challenge

_CAMPUS = "csub"


def _make_challenge(db, *, required: int, optional: int) -> Challenge:
    """Seed a published challenge with ``required`` required then ``optional`` optional
    tasks. Published so build_passport (which only surfaces published challenges)
    finds it."""
    challenge = Challenge(
        campus_id=_CAMPUS,
        name="Test Challenge",
        theme_id="stranger-things",
        semester="Fall 2026",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 10, 1),
        status="published",
    )
    db.add(challenge)
    db.flush()
    position = 1
    for _ in range(required):
        db.add(_task(challenge.id, position, required=True))
        position += 1
    for _ in range(optional):
        db.add(_task(challenge.id, position, required=False))
        position += 1
    db.commit()
    return challenge


def _task(challenge_id: int, position: int, *, required: bool) -> Task:
    return Task(
        challenge_id=challenge_id,
        position=position,
        title=f"Week {position}",
        caption="caption",
        activity_type="Screening",
        location="SHS Clinic",
        date_window_start=date(2026, 9, 1),
        date_window_end=date(2026, 9, 5),
        prize="prize",
        required=required,
    )


def _student(db) -> Student:
    student = Student(
        campus_id=_CAMPUS, sso_subject="abc@csub.edu", affiliation="student"
    )
    db.add(student)
    db.commit()
    return student


def _complete(db, student_id: int, week_nos: list[int]) -> None:
    tasks = db.execute(select(Task).order_by(Task.position)).scalars()
    task_ids = {t.position: t.id for t in tasks}
    for wk in week_nos:
        db.add(CheckIn(student_id=student_id, task_id=task_ids[wk], method="manual"))
    db.commit()


# --- Gherkin scenario 1: not yet eligible while required tasks remain ------------


def test_not_yet_eligible_while_required_tasks_remain(db_sessionmaker):
    with db_sessionmaker() as db:
        _make_challenge(db, required=4, optional=0)
        student = _student(db)
        _complete(db, student.id, [1, 2])  # 2 of 4 required

        view = build_passport(db, campus_id=_CAMPUS, student_id=student.id)

    assert view is not None
    assert view.required_total == 4
    assert view.required_completed == 2
    assert view.prize_eligible is False


# --- Gherkin scenario 2: eligible once all required tasks are complete -----------


def test_eligible_once_all_required_complete(db_sessionmaker):
    with db_sessionmaker() as db:
        _make_challenge(db, required=4, optional=0)
        student = _student(db)
        _complete(db, student.id, [1, 2, 3, 4])  # all 4 required

        view = build_passport(db, campus_id=_CAMPUS, student_id=student.id)

    assert view is not None
    assert view.required_completed == view.required_total == 4
    assert view.prize_eligible is True


# --- Gherkin scenario 3: eligibility ignores non-required tasks ------------------


def test_eligibility_ignores_incomplete_optional_task(db_sessionmaker):
    with db_sessionmaker() as db:
        # 4 required (weeks 1-4) + 1 optional (week 5).
        _make_challenge(db, required=4, optional=1)
        student = _student(db)
        _complete(db, student.id, [1, 2, 3, 4])  # all required, optional left undone

        view = build_passport(db, campus_id=_CAMPUS, student_id=student.id)

    assert view is not None
    # The optional week 5 is still incomplete...
    assert view.weeks[4].is_required is False
    assert view.weeks[4].status != "complete"
    # ...yet the student is prize eligible.
    assert view.prize_eligible is True


def test_completing_only_optional_task_is_not_eligible(db_sessionmaker):
    with db_sessionmaker() as db:
        _make_challenge(db, required=4, optional=1)
        student = _student(db)
        _complete(db, student.id, [5])  # only the optional task

        view = build_passport(db, campus_id=_CAMPUS, student_id=student.id)

    assert view is not None
    assert view.required_completed == 0
    assert view.prize_eligible is False


def test_all_optional_challenge_is_never_eligible(db_sessionmaker):
    # No required tasks at all: eligibility should not be vacuously true.
    with db_sessionmaker() as db:
        _make_challenge(db, required=0, optional=2)
        student = _student(db)
        _complete(db, student.id, [1, 2])  # complete every (optional) task

        view = build_passport(db, campus_id=_CAMPUS, student_id=student.id)

    assert view is not None
    assert view.required_total == 0
    assert view.prize_eligible is False


# --- End-to-end over the API + seeded demo challenge (6 required, 1 optional) ----


def _sign_in(client):
    client.post(
        "/auth/acs",
        data={"subject": "abc@csub.edu", "affiliation": "student", "returnTo": "/app"},
    )


def _student_id(db_sessionmaker):
    with db_sessionmaker() as db:
        return db.execute(select(Student)).scalars().one().id


def _complete_weeks(db_sessionmaker, student_id, week_nos):
    with db_sessionmaker() as db:
        _complete(db, student_id, week_nos)


def test_api_reports_prize_fields_and_not_eligible_initially(client, db_sessionmaker):
    with db_sessionmaker() as db:
        seed_demo_challenge(db)
    _sign_in(client)

    body = client.get("/api/passport").json()
    # Demo seed: week 1 optional, weeks 2-7 required → 6 required tasks.
    assert body["requiredTotal"] == 6
    assert body["requiredCompleted"] == 0
    assert body["prizeEligible"] is False


def test_api_eligible_once_all_required_weeks_complete(client, db_sessionmaker):
    with db_sessionmaker() as db:
        seed_demo_challenge(db)
    _sign_in(client)
    # Complete every required week (2-7); leave the optional week 1 undone.
    _complete_weeks(db_sessionmaker, _student_id(db_sessionmaker), [2, 3, 4, 5, 6, 7])

    body = client.get("/api/passport").json()
    assert body["requiredCompleted"] == body["requiredTotal"] == 6
    assert body["prizeEligible"] is True
    # Optional week 1 remains incomplete, proving eligibility ignores it.
    assert body["weeks"][0]["required"] is False
    assert body["weeks"][0]["status"] != "complete"
