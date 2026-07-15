"""Edge cases for FR-D6 — Manual completion override + audit (US-27).

The two Gherkin scenarios themselves are executed by test_manual_override_bdd.py
against tests/features/manual_override.feature. This module covers what the
scenarios leave implicit: the "correct" half of "remove or correct", the conflict
and validation paths, campus isolation, ledger durability, and the auth guards.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.challenge import CheckIn, CheckInAudit
from app.models.student import Student

ADMIN = "admin@csub.edu"
STUDENT = "student@csub.edu"
REASON = "Scanner was down at the booth."


# ---------------------------------------------------------------------------
# Helpers (mirrors the pattern in test_assessment_items.py)
# ---------------------------------------------------------------------------


def _sign_in_as(client, affiliation: str, subject: str = ADMIN) -> None:
    client.post(
        "/auth/acs",
        data={"subject": subject, "affiliation": affiliation, "returnTo": "/app"},
    )


def _setup(client):
    """Sign in as admin with a challenge + task and a known student. Returns ids."""
    _sign_in_as(client, "student", STUDENT)  # mint the Student row via the IdP
    _sign_in_as(client, "staff", ADMIN)  # ...then restore the admin session

    challenge = client.post(
        "/api/challenges",
        json={
            "name": "Fall 2025 Wellness",
            "semester": "Fall 2025",
            "start_date": "2025-09-01",
            "end_date": "2025-12-15",
        },
    ).json()
    task = client.post(
        f"/api/challenges/{challenge['id']}/tasks",
        json={"title": "Week 2 - Nutrition", "required": True},
    ).json()
    return challenge["id"], task["id"]


def _mark(client, cid, tid, **overrides):
    payload = {"student_subject": STUDENT, "reason": REASON, **overrides}
    return client.post(f"/api/challenges/{cid}/tasks/{tid}/checkins", json=payload)


def _remove(client, cid, tid, checkin_id, reason=REASON):
    # httpx has no client.delete(json=...) — the body must go through .request().
    return client.request(
        "DELETE",
        f"/api/challenges/{cid}/tasks/{tid}/checkins/{checkin_id}",
        json={"reason": reason},
    )


def _correct(client, cid, tid, checkin_id, **body):
    return client.patch(
        f"/api/challenges/{cid}/tasks/{tid}/checkins/{checkin_id}",
        json={"reason": REASON, **body},
    )


def _audits(client, cid, tid, **params):
    return client.get(f"/api/challenges/{cid}/tasks/{tid}/audits", params=params).json()


# ---------------------------------------------------------------------------
# Manual create
# ---------------------------------------------------------------------------


class TestManualCreate:
    def test_marks_student_complete_as_manual(self, client):
        cid, tid = _setup(client)
        resp = _mark(client, cid, tid)
        assert resp.status_code == 201
        body = resp.json()
        assert body["method"] == "manual"
        assert body["student_subject"] == STUDENT
        # The first code in the repo to write verified_by.
        assert body["verified_by"] == ADMIN

    def test_admin_can_backdate_the_completion(self, client):
        cid, tid = _setup(client)
        resp = _mark(client, cid, tid, ts="2025-09-08T12:00:00+00:00")
        assert resp.status_code == 201
        assert resp.json()["ts"].startswith("2025-09-08T12:00:00")

    def test_second_mark_conflicts_rather_than_upserting(self, client):
        cid, tid = _setup(client)
        assert _mark(client, cid, tid).status_code == 201
        resp = _mark(client, cid, tid)
        # Overriding an existing completion is a different audit action, so the
        # caller must say which they meant instead of silently upserting.
        assert resp.status_code == 409
        assert "already has a check-in" in resp.json()["detail"]

    def test_conflict_writes_no_audit_row(self, client):
        cid, tid = _setup(client)
        _mark(client, cid, tid)
        _mark(client, cid, tid)  # 409
        assert len(_audits(client, cid, tid)) == 1  # not 2

    def test_blank_reason_is_rejected(self, client):
        cid, tid = _setup(client)
        assert _mark(client, cid, tid, reason="").status_code == 422

    def test_whitespace_only_reason_is_rejected(self, client):
        cid, tid = _setup(client)
        # Field(min_length=1) would accept this; the field_validator is what bites.
        assert _mark(client, cid, tid, reason="   ").status_code == 422

    def test_unknown_student_subject_is_404(self, client):
        cid, tid = _setup(client)
        resp = _mark(client, cid, tid, student_subject="ghost@csub.edu")
        assert resp.status_code == 404
        assert "signed in" in resp.json()["detail"]

    def test_student_from_another_campus_is_404(self, client, db_sessionmaker):
        cid, tid = _setup(client)
        # The mock IdP always resolves to campus_id="csub", so a foreign-campus
        # student can only be created directly — this is the only way to prove
        # the campus filter on the lookup actually holds.
        with db_sessionmaker() as db:
            db.add(
                Student(
                    campus_id="other",
                    sso_subject="rival@other.edu",
                    affiliation="student",
                )
            )
            db.commit()
        resp = _mark(client, cid, tid, student_subject="rival@other.edu")
        assert resp.status_code == 404

    def test_unknown_task_is_404(self, client):
        cid, _ = _setup(client)
        assert _mark(client, cid, 9999).status_code == 404


# ---------------------------------------------------------------------------
# Correct — the "or correct it" half of the second Gherkin scenario
# ---------------------------------------------------------------------------


class TestCorrectCheckIn:
    def test_correcting_method_preserves_prior_state(self, client):
        cid, tid = _setup(client)
        checkin_id = _mark(client, cid, tid).json()["id"]

        resp = _correct(client, cid, tid, checkin_id, method="staff")
        assert resp.status_code == 200
        assert resp.json()["method"] == "staff"

        audit = _audits(client, cid, tid)[0]
        assert audit["action"] == "update"
        assert audit["prior_state"]["method"] == "manual"
        assert audit["new_state"]["method"] == "staff"
        assert audit["actor_subject"] == ADMIN
        assert audit["reason"] == REASON

    def test_correcting_timestamp_is_audited(self, client):
        cid, tid = _setup(client)
        checkin_id = _mark(client, cid, tid).json()["id"]
        resp = _correct(client, cid, tid, checkin_id, ts="2025-09-08T12:00:00+00:00")
        assert resp.status_code == 200

        audit = _audits(client, cid, tid)[0]
        assert audit["action"] == "update"
        assert audit["prior_state"]["ts"] != audit["new_state"]["ts"]

    def test_blank_reason_is_rejected(self, client):
        cid, tid = _setup(client)
        checkin_id = _mark(client, cid, tid).json()["id"]
        resp = _correct(client, cid, tid, checkin_id, reason="  ", method="staff")
        assert resp.status_code == 422

    def test_unknown_checkin_is_404(self, client):
        cid, tid = _setup(client)
        assert _correct(client, cid, tid, 9999, method="staff").status_code == 404

    def test_checkin_of_another_task_is_404(self, client):
        cid, tid = _setup(client)
        checkin_id = _mark(client, cid, tid).json()["id"]
        other = client.post(
            f"/api/challenges/{cid}/tasks", json={"title": "Week 3", "required": True}
        ).json()
        # Same challenge, wrong task — must not be reachable.
        assert _correct(client, cid, other["id"], checkin_id).status_code == 404


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


class TestRemoveCheckIn:
    def test_removes_the_checkin_and_audits_it(self, client):
        cid, tid = _setup(client)
        checkin_id = _mark(client, cid, tid).json()["id"]

        assert _remove(client, cid, tid, checkin_id).status_code == 204
        assert client.get(f"/api/challenges/{cid}/tasks/{tid}/checkins").json() == []

        audits = _audits(client, cid, tid)
        assert [a["action"] for a in audits] == ["delete", "create"]
        assert audits[0]["new_state"] is None
        assert audits[0]["prior_state"]["method"] == "manual"

    def test_blank_reason_is_rejected(self, client):
        cid, tid = _setup(client)
        checkin_id = _mark(client, cid, tid).json()["id"]
        assert _remove(client, cid, tid, checkin_id, reason="").status_code == 422

    def test_reason_is_required_even_to_delete(self, client):
        cid, tid = _setup(client)
        checkin_id = _mark(client, cid, tid).json()["id"]
        resp = client.request(
            "DELETE", f"/api/challenges/{cid}/tasks/{tid}/checkins/{checkin_id}", json={}
        )
        assert resp.status_code == 422

    def test_unknown_checkin_is_404(self, client):
        cid, tid = _setup(client)
        assert _remove(client, cid, tid, 9999).status_code == 404


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------


class TestAuditTrail:
    def test_actions_accumulate_newest_first(self, client):
        cid, tid = _setup(client)
        checkin_id = _mark(client, cid, tid).json()["id"]
        _correct(client, cid, tid, checkin_id, method="staff")
        _remove(client, cid, tid, checkin_id)

        assert [a["action"] for a in _audits(client, cid, tid)] == [
            "delete",
            "update",
            "create",
        ]

    def test_filters_by_student_subject(self, client):
        cid, tid = _setup(client)
        _mark(client, cid, tid)

        # A second student with their own manual completion on the same task.
        _sign_in_as(client, "student", "other@csub.edu")
        _sign_in_as(client, "staff", ADMIN)
        _mark(client, cid, tid, student_subject="other@csub.edu")

        assert len(_audits(client, cid, tid)) == 2
        filtered = _audits(client, cid, tid, student_subject=STUDENT)
        assert len(filtered) == 1
        assert filtered[0]["new_state"]["student_subject"] == STUDENT

    def test_unknown_filter_subject_is_404(self, client):
        cid, tid = _setup(client)
        resp = client.get(
            f"/api/challenges/{cid}/tasks/{tid}/audits",
            params={"student_subject": "ghost@csub.edu"},
        )
        assert resp.status_code == 404

    def test_audit_survives_deletion_of_the_task(self, client, db_sessionmaker):
        """The reason checkin_audits carries no foreign keys.

        CheckIn.task_id is declared ondelete="CASCADE", so on a backend that
        enforces foreign keys, deleting a task takes its check-ins with it. Were
        the ledger FK'd to tasks or checkins it would be cascaded away too —
        destroying exactly the evidence FR-D6 exists to guarantee. Being FK-free,
        it survives, and its snapshots stay readable with the task gone.

        The check-in's own fate is deliberately not asserted: SQLite ships with
        PRAGMA foreign_keys=OFF and this app never enables it, so the cascade is
        inert here but would fire on Postgres. The ledger outlives the task either
        way, which is the whole claim.
        """
        cid, tid = _setup(client)
        _mark(client, cid, tid)

        assert client.delete(f"/api/challenges/{cid}/tasks/{tid}").status_code == 204
        # The task is really gone — the task-scoped endpoints 404 now.
        assert client.get(f"/api/challenges/{cid}/tasks/{tid}/audits").status_code == 404

        # ...so read the ledger directly.
        with db_sessionmaker() as db:
            rows = db.query(CheckInAudit).filter(CheckInAudit.task_id == tid).all()
            assert len(rows) == 1
            assert rows[0].action == "create"
            assert rows[0].actor_subject == ADMIN
            assert rows[0].reason == REASON
            # The snapshot is self-contained — still readable with the task gone.
            assert rows[0].new_state["student_subject"] == STUDENT
            assert rows[0].new_state["method"] == "manual"

    def test_snapshot_timestamp_is_json_serializable(self, client, db_sessionmaker):
        """_snapshot must isoformat ts — the JSON column cannot hold a datetime."""
        cid, tid = _setup(client)
        _mark(client, cid, tid, ts="2025-09-08T12:00:00+00:00")
        with db_sessionmaker() as db:
            audit = db.query(CheckInAudit).one()
            assert isinstance(audit.new_state["ts"], str)
            assert audit.new_state["ts"].startswith("2025-09-08T12:00:00")


# ---------------------------------------------------------------------------
# Auth guards (the repo-wide pair)
# ---------------------------------------------------------------------------


class TestAuthGuards:
    def _seed_checkin(self, client, db_sessionmaker):
        """Seed a check-in via the ORM so a non-admin has something to attack."""
        cid, tid = _setup(client)
        with db_sessionmaker() as db:
            student = db.query(Student).filter(Student.sso_subject == STUDENT).one()
            checkin = CheckIn(
                student_id=student.id,
                task_id=tid,
                ts=datetime(2025, 9, 8, tzinfo=timezone.utc),
                method="event_qr",
            )
            db.add(checkin)
            db.commit()
            db.refresh(checkin)
            return cid, tid, checkin.id

    def test_student_cannot_mark_complete(self, client):
        cid, tid = _setup(client)
        _sign_in_as(client, "student", STUDENT)
        assert _mark(client, cid, tid).status_code == 403

    def test_student_cannot_read_the_audit_trail(self, client):
        cid, tid = _setup(client)
        _sign_in_as(client, "student", STUDENT)
        resp = client.get(f"/api/challenges/{cid}/tasks/{tid}/audits")
        assert resp.status_code == 403

    def test_student_cannot_remove_a_checkin(self, client, db_sessionmaker):
        cid, tid, checkin_id = self._seed_checkin(client, db_sessionmaker)
        _sign_in_as(client, "student", STUDENT)
        assert _remove(client, cid, tid, checkin_id).status_code == 403

    def test_unauthenticated_cannot_mark_complete(self, client):
        cid, tid = _setup(client)
        client.cookies.clear()
        assert _mark(client, cid, tid).status_code == 401

    def test_unauthenticated_cannot_read_the_audit_trail(self, client):
        cid, tid = _setup(client)
        client.cookies.clear()
        assert client.get(f"/api/challenges/{cid}/tasks/{tid}/audits").status_code == 401
