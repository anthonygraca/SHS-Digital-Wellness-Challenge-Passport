from __future__ import annotations

# The friendly copy shown when a non-current student is blocked. Kept here so the
# gate dependency and any surfacing route share one source of truth (FR-A3).
NOT_CURRENT_STUDENT_CODE = "not_current_student"
NOT_CURRENT_STUDENT_MESSAGE = (
    "Participation is limited to current students. If you believe this is a "
    "mistake, please contact Student Health Services."
)


def is_current_student(affiliation: str) -> bool:
    """Whether the IdP-asserted affiliation marks a current student (FR-A3).

    Exact match on the standard ``eduPersonAffiliation`` value ``student`` — past
    students (``alum``) and other affiliations are not current students. Using an
    exact match (not a substring) avoids mis-classifying values like ``non-student``.
    """
    return affiliation.strip().lower() == "student"
