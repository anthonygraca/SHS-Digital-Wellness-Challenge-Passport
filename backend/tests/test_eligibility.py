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


def test_current_student_passes_eligibility_gate(client):
    """A current student is not blocked by the gate. With no challenge seeded the
    enrollment logic responds 404 no_active_challenge — proving we got *past* the
    401/403 gate into the enrollment body. Enrollment itself is covered in
    test_enrollment.py."""
    _sign_in(client, "student")
    resp = client.post("/enrollment")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "no_active_challenge"


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
