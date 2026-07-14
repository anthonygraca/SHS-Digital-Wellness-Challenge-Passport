from __future__ import annotations

import pytest

from app.auth.eligibility import is_current_student


def _sign_in(client, affiliation: str):
    """Sign in via the ACS (following the redirect) so the client holds the cookie."""
    return client.post(
        "/auth/acs",
        data={
            "subject": "abc@csub.edu",
            "affiliation": affiliation,
            "returnTo": "/app",
        },
    )


# --- Unit: current-student detection (FR-A3) ------------------------------------


@pytest.mark.parametrize("affiliation", ["student", "STUDENT", " student ", "Student"])
def test_is_current_student_true_for_student_value(affiliation):
    assert is_current_student(affiliation) is True


@pytest.mark.parametrize(
    "affiliation", ["alum", "non-student", "faculty", "staff", "member", ""]
)
def test_is_current_student_false_for_non_students(affiliation):
    assert is_current_student(affiliation) is False


# --- US-2 Gherkin scenario 1: current student passes the eligibility gate --------


def test_current_student_may_enroll(client):
    _sign_in(client, "student")
    resp = client.post("/enrollment")
    assert resp.status_code == 200
    assert resp.json() == {"eligible": True}


# --- US-2 Gherkin scenario 2: non-current student is blocked ---------------------


def test_non_current_student_is_blocked_with_friendly_message(client):
    _sign_in(client, "alum")
    resp = client.post("/enrollment")
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["code"] == "not_current_student"
    assert detail["message"]  # a non-empty, friendly explanation


def test_enrollment_requires_sign_in(client):
    assert client.post("/enrollment").status_code == 401
