"""Contract tests: the Repository protocol must behave identically on both backends.

Every test here runs twice — against ``SqlAlchemyRepository`` (in-memory SQLite) and
``DynamoRepository`` (moto, tables built from ``template.yaml``). This is the guard the
Dynamo port relies on: production runs Dynamo, but until this suite existed only the SQL
path was exercised (the route tests bind SQL). Each later PR that adds a method to the
``Repository`` protocol extends this suite in the same commit.

With ``WP_DDB_ENDPOINT_URL`` set, the dynamo parameter runs against DynamoDB Local
instead of moto (see tests/ddb_support.py) — the same assertions, AWS's own engine.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.repositories.sqlalchemy_repo import SqlAlchemyRepository
from app.schemas.challenge import (
    ChallengeCreate,
    ChallengeUpdate,
    MCQCreate,
    TaskCreate,
    TaskReorder,
)
from app.schemas.theme import ThemeCreate, ThemeUpdate
from app.services.passport import DuplicateCheckIn, InvalidEventToken
from app.services.qr import mint_event_token
from tests.ddb_support import dynamo_backend, set_env


@pytest.fixture(params=["sql", "dynamo"])
def repo(request, monkeypatch):
    if request.param == "sql":
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        # expire_on_commit=True so a read after a write re-queries rather than serving a
        # cached ORM relationship. Production gets this for free — a fresh session per
        # request — but the contract reuses one session across operations, and without
        # this the SQL path would report stale post-delete tasks while Dynamo (fresh
        # DTOs each call) reports the truth. The contract is about observable behavior on
        # independent reads, which is what expiring gives us.
        db = sessionmaker(bind=engine, autoflush=False, expire_on_commit=True)()
        try:
            yield SqlAlchemyRepository(db)
        finally:
            db.close()
            engine.dispose()
    else:
        from app.config import get_settings
        from app.repositories.dynamo_repo import DynamoRepository, reset_tables

        set_env(monkeypatch)
        get_settings.cache_clear()
        with dynamo_backend():
            reset_tables()
            yield DynamoRepository()
        reset_tables()
        get_settings.cache_clear()


# --- helpers ----------------------------------------------------------------
def _challenge(repo, name="Fall", semester="Fall 2026", publish=True):
    ch = repo.create_challenge(
        "csub",
        ChallengeCreate(
            name=name,
            semester=semester,
            start_date="2026-09-01",
            end_date="2026-12-01",
        ),
    )
    if publish:
        repo.publish_challenge("csub", ch.id)
    return ch


def _built_challenge(repo, titles=("Week 1", "Week 2")):
    """A published challenge with tasks — built draft-first, the real order."""
    ch = _challenge(repo, publish=False)
    tasks = [repo.add_task(ch.id, TaskCreate(title=t)) for t in titles]
    repo.publish_challenge("csub", ch.id)
    return ch, tasks


def _student(repo, sso="stu@csub.edu"):
    return repo.get_or_create_student("csub", sso, "student")


def _theme(repo, id="stranger-things", name="Stranger Things", **kw):
    return repo.create_theme(
        ThemeCreate(
            id=id,
            name=name,
            palette={"primary": "#ff4438"},
            logo_url="https://cdn.example.edu/logo.png",
            **kw,
        )
    )


# --- challenges -------------------------------------------------------------
def test_ids_increment_from_one(repo):
    a = _challenge(repo, name="A", publish=False)
    b = _challenge(repo, name="B", publish=False)
    assert (a.id, b.id) == (1, 2)


def test_only_published_is_active_and_latest_start_wins(repo):
    assert repo.get_active_challenge("csub") is None
    _challenge(repo, name="Draft", publish=False)
    assert repo.get_active_challenge("csub") is None  # a draft is not active

    early = repo.create_challenge(
        "csub",
        ChallengeCreate(
            name="Early", semester="S1", start_date="2026-01-01", end_date="2026-02-01"
        ),
    )
    repo.publish_challenge("csub", early.id)
    late = _challenge(repo, name="Late")  # starts 2026-09-01
    active = repo.get_active_challenge("csub")
    assert active is not None and active.id == late.id


def test_active_challenge_is_campus_scoped(repo):
    _challenge(repo)
    assert repo.get_active_challenge("other-campus") is None


# --- tasks ------------------------------------------------------------------
def test_task_positions_reorder_and_delete_closes_the_gap(repo):
    ch = _challenge(repo, publish=False)
    t1 = repo.add_task(ch.id, TaskCreate(title="W1"))
    t2 = repo.add_task(ch.id, TaskCreate(title="W2"))
    t3 = repo.add_task(ch.id, TaskCreate(title="W3"))
    assert [t1.position, t2.position, t3.position] == [1, 2, 3]

    repo.reorder_tasks(ch.id, TaskReorder(task_ids=[t3.id, t1.id, t2.id]))
    full = repo.get_challenge("csub", ch.id)
    assert [(t.id, t.position) for t in full.tasks] == [
        (t3.id, 1),
        (t1.id, 2),
        (t2.id, 3),
    ]

    repo.delete_task(ch.id, t1.id)  # was position 2
    full = repo.get_challenge("csub", ch.id)
    assert [t.position for t in full.tasks] == [1, 2]  # gap closed
    assert t1.id not in {t.id for t in full.tasks}


def test_reorder_rejects_a_wrong_id_set(repo):
    ch = _challenge(repo, publish=False)
    t1 = repo.add_task(ch.id, TaskCreate(title="W1"))
    with pytest.raises(ValueError):
        repo.reorder_tasks(ch.id, TaskReorder(task_ids=[t1.id, 999]))


# --- assessment items -------------------------------------------------------
def test_assessment_item_crud(repo):
    ch = _challenge(repo, publish=False)
    t = repo.add_task(ch.id, TaskCreate(title="W1"))
    item = repo.add_item(
        t.id,
        MCQCreate(
            item_type="mcq",
            prompt="Q?",
            outcome_tag="vision-care",
            options=["a", "b"],
            answer_key="a",
        ),
    )
    assert repo.get_item(t.id, item.id) is not None
    assert [i.id for i in repo.list_items(t.id)] == [item.id]

    repo.delete_item(t.id, item.id)
    assert repo.get_item(t.id, item.id) is None
    assert repo.list_items(t.id) == []


# --- enrollment + students --------------------------------------------------
def test_enrollment_is_idempotent(repo):
    ch = _challenge(repo)
    stu = _student(repo)
    first = repo.enroll(stu.id, ch.id)
    second = repo.enroll(stu.id, ch.id)
    assert first.id == second.id
    assert repo.get_enrollment(stu.id, ch.id) is not None


def test_get_or_create_student_is_idempotent(repo):
    a = repo.get_or_create_student("csub", "sam@csub.edu", "student")
    b = repo.get_or_create_student("csub", "sam@csub.edu", "student")
    assert a.id == b.id


# --- passport (derived reads) + check-in writes -----------------------------
def test_passport_sequential_unlock_and_prize_eligibility(repo):
    ch, (t1, t2) = _built_challenge(repo)
    stu = _student(repo)

    view = repo.build_passport("csub", stu.id)
    assert [w.status for w in view.weeks] == ["available", "locked"]
    assert view.prize_eligible is False

    task, view = repo.record_event_qr_checkin("csub", stu.id, mint_event_token(t1.id))
    assert task.position == 1
    # The returned passport reflects the check-in without a second challenge lookup.
    assert [w.status for w in view.weeks] == ["complete", "available"]
    assert view.completed_weeks == 1
    assert view.prize_eligible is False

    _, view = repo.record_event_qr_checkin("csub", stu.id, mint_event_token(t2.id))
    assert view.prize_eligible is True  # every required task complete


def test_checkin_is_idempotent_and_tokens_are_validated(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    stu = _student(repo)
    token = mint_event_token(t1.id)

    repo.record_event_qr_checkin("csub", stu.id, token)
    with pytest.raises(DuplicateCheckIn):
        repo.record_event_qr_checkin("csub", stu.id, token)
    with pytest.raises(InvalidEventToken):
        repo.record_event_qr_checkin("csub", stu.id, "not-a-real-token")


def test_completed_tasks_are_scoped_to_the_student(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    alice = _student(repo, "alice@csub.edu")
    bob = _student(repo, "bob@csub.edu")

    repo.record_event_qr_checkin("csub", alice.id, mint_event_token(t1.id))

    # Alice's check-in must not bleed into Bob's passport.
    bob_view = repo.build_passport("csub", bob.id)
    assert [w.status for w in bob_view.weeks] == ["available"]
    alice_view = repo.build_passport("csub", alice.id)
    assert [w.status for w in alice_view.weeks] == ["complete"]


# --- assessments (FR-E4 / FR-E5) --------------------------------------------
def _mcq(repo, task_id, tag="vision-care"):
    return repo.add_item(
        task_id,
        MCQCreate(
            item_type="mcq",
            prompt="How often?",
            outcome_tag=tag,
            options=["yearly", "never"],
            answer_key="yearly",
        ),
    )


def test_a_fractional_score_round_trips_as_a_float(repo):
    """The reflection rubric scores fractionally, and boto3 refuses Python floats.

    Without the float -> Decimal encoding this is a hard 500 on the first reflection
    ever scored in production ("Float types are not supported. Use Decimal types
    instead"), and reading it back as Decimal rather than float would quietly change
    the type the FR-F4 mean is computed from.
    """
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    item = _mcq(repo, t1.id)
    stu = _student(repo)

    stored = repo.create_response(
        student_id=stu.id,
        item=item,
        challenge_id=ch.id,
        response="yearly",
        score=0.6,
        scored_by="auto",
        ai_feedback="Good, but say why.",
    )
    assert stored.score == 0.6

    read_back = repo.get_response(stu.id, item.id)
    assert read_back.score == 0.6
    assert isinstance(read_back.score, float)
    assert read_back.ai_feedback == "Good, but say why."


def test_a_response_is_one_attempt(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    item = _mcq(repo, t1.id)
    stu = _student(repo)
    args = dict(
        student_id=stu.id,
        item=item,
        challenge_id=ch.id,
        response="yearly",
        score=1.0,
        scored_by="auto",
    )
    assert repo.create_response(**args) is not None
    # The write itself is the arbiter — a second attempt is refused, not overwritten.
    assert repo.create_response(**{**args, "response": "never", "score": 0.0}) is None
    assert repo.get_response(stu.id, item.id).response == "yearly"


def test_responses_are_scoped_to_the_student(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    item = _mcq(repo, t1.id)
    alice = _student(repo, "alice@csub.edu")
    bob = _student(repo, "bob@csub.edu")
    repo.create_response(
        student_id=alice.id,
        item=item,
        challenge_id=ch.id,
        response="yearly",
        score=1.0,
        scored_by="auto",
    )
    assert repo.get_response(bob.id, item.id) is None
    # Bob may still answer the same item.
    assert (
        repo.create_response(
            student_id=bob.id,
            item=item,
            challenge_id=ch.id,
            response="never",
            score=0.0,
            scored_by="auto",
        )
        is not None
    )


def test_get_responses_for_items_maps_by_item(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    a = _mcq(repo, t1.id, tag="one")
    b = _mcq(repo, t1.id, tag="two")
    stu = _student(repo)
    repo.create_response(
        student_id=stu.id,
        item=a,
        challenge_id=ch.id,
        response="yearly",
        score=1.0,
        scored_by="auto",
    )

    got = repo.get_responses_for_items(stu.id, [a.id, b.id])
    assert set(got) == {a.id}  # only the answered one
    assert got[a.id].score == 1.0
    assert repo.get_responses_for_items(stu.id, []) == {}


def test_get_task_by_position_and_item_challenge_scoping(repo):
    ch, (t1, t2) = _built_challenge(repo)
    assert repo.get_task_by_position(ch.id, 1).id == t1.id
    assert repo.get_task_by_position(ch.id, 2).id == t2.id
    assert repo.get_task_by_position(ch.id, 99) is None

    item = _mcq(repo, t1.id)
    assert repo.get_item_in_challenge(ch.id, item.id).id == item.id
    # An item id from another challenge is indistinguishable from one that never was.
    other = _challenge(repo, name="Other", semester="S2", publish=False)
    assert repo.get_item_in_challenge(other.id, item.id) is None


def test_list_item_responses_pairs_with_its_student(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    item = _mcq(repo, t1.id)
    alice = _student(repo, "alice@csub.edu")
    bob = _student(repo, "bob@csub.edu")
    for s, ans in ((alice, "yearly"), (bob, "never")):
        repo.create_response(
            student_id=s.id,
            item=item,
            challenge_id=ch.id,
            response=ans,
            score=1.0 if ans == "yearly" else 0.0,
            scored_by="auto",
        )

    pairs = repo.list_item_responses(item.id)
    assert len(pairs) == 2
    assert {st.sso_subject for _r, st in pairs} == {"alice@csub.edu", "bob@csub.edu"}
    for r, st in pairs:
        assert r.student_id == st.id


def test_get_item_response_is_scoped_to_its_item(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    a = _mcq(repo, t1.id, tag="one")
    b = _mcq(repo, t1.id, tag="two")
    stu = _student(repo)
    resp = repo.create_response(
        student_id=stu.id,
        item=a,
        challenge_id=ch.id,
        response="yearly",
        score=1.0,
        scored_by="auto",
    )
    assert repo.get_item_response(a.id, resp.id).id == resp.id
    # A response id from another item is a 404, not an override on the wrong question.
    assert repo.get_item_response(b.id, resp.id) is None


def test_override_sets_a_human_score_and_keeps_the_feedback(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    item = _mcq(repo, t1.id)
    stu = _student(repo)
    resp = repo.create_response(
        student_id=stu.id,
        item=item,
        challenge_id=ch.id,
        response="never",
        score=0.0,
        scored_by="auto",
        ai_feedback="The machine said this.",
    )

    updated = repo.override_response_score(resp, 0.75)
    assert updated.score == 0.75
    assert updated.scored_by == "human"
    # The feedback is the only record of what was overridden — never cleared.
    assert updated.ai_feedback == "The machine said this."

    stored = repo.get_response(stu.id, item.id)
    assert stored.score == 0.75
    assert stored.scored_by == "human"
    assert stored.ai_feedback == "The machine said this."


# --- content views (FR-F3 / US-23) ------------------------------------------
def test_content_views_count_views_not_viewers(repo):
    ch, (t1, t2) = _built_challenge(repo)
    stu = _student(repo)
    assert repo.count_content_views(ch.id) == {}

    repo.record_content_view(student_id=stu.id, task=t1, content_ref="week_detail")
    # The same student re-reading the same week counts again: no unique constraint,
    # deliberately — re-reading is engagement, not a duplicate.
    repo.record_content_view(student_id=stu.id, task=t1, content_ref="week_detail")
    repo.record_content_view(student_id=stu.id, task=t2, content_ref="tip")

    assert repo.count_content_views(ch.id) == {"week_detail": 2, "tip": 1}


def test_content_views_are_scoped_to_their_challenge(repo):
    ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    stu = _student(repo)
    repo.record_content_view(student_id=stu.id, task=t1, content_ref="week_detail")

    other = _challenge(repo, name="Other", semester="S2", publish=False)
    assert repo.count_content_views(other.id) == {}


# --- manual completion override + audit (FR-D6 / US-27) ---------------------
def test_manual_checkin_writes_the_checkin_and_its_audit_row(repo):
    _ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    stu = _student(repo)

    checkin = repo.create_manual_checkin(
        campus_id="csub",
        task=t1,
        student=stu,
        actor_subject="admin@csub.edu",
        reason="Signed the paper sheet at the door",
    )
    assert checkin.method == "manual"
    assert checkin.verified_by == "admin@csub.edu"
    # It counts as a completion on the student's passport.
    assert [w.status for w in repo.build_passport("csub", stu.id).weeks] == ["complete"]

    audits = repo.list_task_audits(t1.id)
    assert len(audits) == 1
    assert audits[0].action == "create"
    assert audits[0].actor_subject == "admin@csub.edu"
    assert audits[0].reason == "Signed the paper sheet at the door"
    assert audits[0].prior_state is None
    assert audits[0].new_state["student_subject"] == "stu@csub.edu"
    assert audits[0].new_state["method"] == "manual"


def test_manual_checkin_refuses_a_duplicate(repo):
    _ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    stu = _student(repo)
    args = dict(campus_id="csub", task=t1, student=stu, actor_subject="admin", reason="r")
    repo.create_manual_checkin(**args)
    # An existing completion is an override, not a create — the router 409s on this.
    with pytest.raises(ValueError):
        repo.create_manual_checkin(**args)
    # And the refusal left no second audit row behind.
    assert len(repo.list_task_audits(t1.id)) == 1


def test_a_scanned_checkin_blocks_a_manual_one_for_the_same_week(repo):
    _ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    stu = _student(repo)
    repo.record_event_qr_checkin("csub", stu.id, mint_event_token(t1.id))
    with pytest.raises(ValueError):
        repo.create_manual_checkin(
            campus_id="csub", task=t1, student=stu, actor_subject="admin", reason="r"
        )


def test_get_and_list_checkins_for_a_task(repo):
    _ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    alice = _student(repo, "alice@csub.edu")
    bob = _student(repo, "bob@csub.edu")
    a = repo.create_manual_checkin(
        campus_id="csub", task=t1, student=alice, actor_subject="admin", reason="r"
    )
    repo.create_manual_checkin(
        campus_id="csub", task=t1, student=bob, actor_subject="admin", reason="r"
    )

    assert repo.get_checkin(t1.id, a.id).student_id == alice.id
    assert repo.get_checkin(t1.id, 99999) is None

    pairs = repo.list_task_checkins(t1.id)
    assert len(pairs) == 2
    # Each check-in is paired with its own student, for subject display.
    assert {s.sso_subject for _c, s in pairs} == {"alice@csub.edu", "bob@csub.edu"}
    for c, s in pairs:
        assert c.student_id == s.id


def test_correct_checkin_records_prior_and_new_state(repo):
    _ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    stu = _student(repo)
    repo.record_event_qr_checkin("csub", stu.id, mint_event_token(t1.id))
    checkin = repo.list_task_checkins(t1.id)[0][0]
    assert checkin.method == "event_qr"

    updated = repo.correct_checkin(
        campus_id="csub",
        checkin=checkin,
        student=stu,
        actor_subject="admin@csub.edu",
        reason="Scanned on the wrong device",
        method="staff",
    )
    assert updated.method == "staff"
    assert updated.verified_by == "admin@csub.edu"
    assert repo.get_checkin(t1.id, checkin.id).method == "staff"

    audit = repo.list_task_audits(t1.id)[0]
    assert audit.action == "update"
    assert audit.prior_state["method"] == "event_qr"
    assert audit.new_state["method"] == "staff"


def test_remove_checkin_keeps_the_prior_state_in_the_ledger(repo):
    _ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    stu = _student(repo)
    checkin = repo.create_manual_checkin(
        campus_id="csub", task=t1, student=stu, actor_subject="admin", reason="r"
    )

    repo.remove_checkin(
        campus_id="csub",
        checkin=checkin,
        student=stu,
        actor_subject="admin@csub.edu",
        reason="Recorded against the wrong student",
    )
    assert repo.get_checkin(t1.id, checkin.id) is None
    assert repo.list_task_checkins(t1.id) == []
    # The week is incomplete again...
    assert [w.status for w in repo.build_passport("csub", stu.id).weeks] == ["available"]

    # ...but the ledger still says it happened, and what it looked like.
    audit = repo.list_task_audits(t1.id)[0]
    assert audit.action == "delete"
    assert audit.new_state is None
    assert audit.prior_state["student_subject"] == "stu@csub.edu"
    assert audit.prior_state["method"] == "manual"


def test_the_ledger_is_newest_first_and_filterable_by_student(repo):
    _ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    alice = _student(repo, "alice@csub.edu")
    bob = _student(repo, "bob@csub.edu")
    a = repo.create_manual_checkin(
        campus_id="csub", task=t1, student=alice, actor_subject="admin", reason="first"
    )
    repo.create_manual_checkin(
        campus_id="csub", task=t1, student=bob, actor_subject="admin", reason="second"
    )
    repo.remove_checkin(
        campus_id="csub",
        checkin=a,
        student=alice,
        actor_subject="admin",
        reason="third",
    )

    assert [x.reason for x in repo.list_task_audits(t1.id)] == [
        "third",
        "second",
        "first",
    ]
    assert [x.reason for x in repo.list_task_audits(t1.id, alice.id)] == [
        "third",
        "first",
    ]


def test_a_refused_checkin_leaves_no_orphan_audit_row(repo):
    """The FR-D6 invariant: the check-in and its audit row move together.

    services/checkins.py calls this load-bearing — a completion must never change
    without leaving a trace, and equally no trace may claim a change that never
    happened. SQL gets it from one commit; Dynamo needs TransactWriteItems, and a
    naive two-put port would half-apply here and the ledger would quietly lie.
    """
    _ch, (t1,) = _built_challenge(repo, titles=("Week 1",))
    stu = _student(repo)
    repo.create_manual_checkin(
        campus_id="csub", task=t1, student=stu, actor_subject="admin", reason="real"
    )

    with pytest.raises(ValueError):
        repo.create_manual_checkin(
            campus_id="csub",
            task=t1,
            student=stu,
            actor_subject="admin",
            reason="never happened",
        )

    # Exactly one check-in, exactly one audit row: the refused write rolled back
    # whole, rather than leaving its audit row behind.
    assert len(repo.list_task_checkins(t1.id)) == 1
    audits = repo.list_task_audits(t1.id)
    assert len(audits) == 1
    assert audits[0].reason == "real"
    assert "never happened" not in [a.reason for a in audits]


# --- themes (FR-B4 / US-13) -------------------------------------------------
def test_theme_create_get_and_list_sorted_by_name(repo):
    assert repo.list_themes() == []
    created = repo.create_theme(
        ThemeCreate(
            id="stranger-things", name="Stranger Things", palette={"primary": "#f43"}
        )
    )
    assert created.id == "stranger-things"

    got = repo.get_theme("stranger-things")
    assert got is not None and got.name == "Stranger Things"
    assert got.palette == {"primary": "#f43"}
    assert repo.get_theme("does-not-exist") is None

    _theme(repo, id="aardvark", name="Aardvark")
    assert [t.name for t in repo.list_themes()] == ["Aardvark", "Stranger Things"]


def test_theme_update_is_partial_and_can_clear_a_field(repo):
    _theme(repo)  # logo_url set, tagline empty

    changed = repo.update_theme(
        "stranger-things", ThemeUpdate(tagline="The gate is open.")
    )
    assert changed.tagline == "The gate is open."
    assert changed.name == "Stranger Things"  # untouched
    assert changed.logo_url == "https://cdn.example.edu/logo.png"  # untouched

    # A field sent as null clears it; unsent fields keep the earlier change.
    cleared = repo.update_theme("stranger-things", ThemeUpdate(logo_url=None))
    assert cleared.logo_url is None
    assert cleared.tagline == "The gate is open."

    assert repo.update_theme("nope", ThemeUpdate(name="x")) is None


def test_passport_carries_the_resolved_theme(repo):
    _theme(repo)
    ch = _challenge(repo, publish=False)
    repo.add_task(ch.id, TaskCreate(title="W1"))
    repo.update_challenge("csub", ch.id, ChallengeUpdate(theme_id="stranger-things"))
    repo.publish_challenge("csub", ch.id)
    stu = _student(repo)

    view = repo.build_passport("csub", stu.id)
    assert view.theme == "stranger-things"
    assert view.theme_config is not None
    assert view.theme_config.id == "stranger-things"
    assert view.theme_config.palette["primary"] == "#ff4438"


def test_passport_theme_config_is_none_without_a_theme(repo):
    # A challenge with no theme_id resolves to the default skin (None), not an error.
    _built_challenge(repo, titles=("W1",))
    stu = _student(repo)
    view = repo.build_passport("csub", stu.id)
    assert view.theme == ""
    assert view.theme_config is None
