from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.config import get_settings

_ALG = "HS256"


def mint_session_token(
    *, sso_subject: str, affiliation: str, campus_id: str, student_id: int
) -> str:
    """Issue a short-lived session JWT. Claims carry no PHI."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sso_subject,
        "affiliation": affiliation,
        "campus_id": campus_id,
        "student_id": student_id,
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALG)


def verify_session_token(token: str) -> Optional[dict]:
    """Return the decoded claims, or None if missing/expired/tampered."""
    if not token:
        return None
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALG])
    except jwt.PyJWTError:
        return None
