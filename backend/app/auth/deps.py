from __future__ import annotations

from fastapi import Request

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
