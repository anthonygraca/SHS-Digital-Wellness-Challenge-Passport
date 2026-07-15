from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.auth.eligibility import (
    NOT_CURRENT_STUDENT_CODE,
    NOT_CURRENT_STUDENT_MESSAGE,
    is_current_student,
)
from app.auth.session import verify_session_token
from app.config import get_settings


def current_claims(request: Request) -> dict | None:
    """Read session claims from the HttpOnly cookie, or a Bearer token as a fallback."""
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie)
    if not token:
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header[7:]
    return verify_session_token(token or "")


def get_current_student(request: Request) -> dict:
    """Get the current authenticated student's claims (US-8, US-15).

    Alias for require_current_student for backward compatibility.
    Returns claims dict with:
    - sub: SSO subject
    - campus_id: Campus identifier
    - student_id: Database student ID
    - role: User role (student or admin)
    """
    return require_current_student(request)


def require_current_student(request: Request) -> dict:
    """Gate a route on current-student eligibility (FR-A3 / US-2).

    Returns the session claims when the caller is a signed-in current student;
    raises 401 if not signed in, or 403 with a friendly ``not_current_student``
    payload the SPA can branch on.
    """
    claims = current_claims(request)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in"
        )
    if not is_current_student(claims.get("affiliation", "")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": NOT_CURRENT_STUDENT_CODE,
                "message": NOT_CURRENT_STUDENT_MESSAGE,
            },
        )
    return claims


def require_admin(request: Request) -> dict:
    """Dependency that enforces an admin/staff role (FR-A4).

    Accepts any session whose ``affiliation`` contains "staff" or "admin"
    (case-insensitive). Raises 401 when there is no valid session at all, and
    403 when the session exists but carries a non-admin affiliation — so that
    student-role callers get a clear "Forbidden" rather than "Not signed in".
    """
    claims = current_claims(request)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not signed in",
        )
    affiliation = claims.get("affiliation", "").lower()
    if "admin" not in affiliation and "staff" not in affiliation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or staff role required",
        )
    return claims
