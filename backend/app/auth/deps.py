from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

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

    Raises 401 if not authenticated. Returns claims dict with:
    - sub: SSO subject
    - campus_id: Campus identifier
    - student_id: Database student ID
    - role: User role (student or admin)
    """
    claims = current_claims(request)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return claims
