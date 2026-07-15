from __future__ import annotations

import jwt

from app.config import get_settings

_ALG = "HS256"
_TYP = "event_qr"


def mint_event_token(task_id: int) -> str:
    """Sign a static event-QR token for a task (US-8).

    The token carries only the task id and a type marker, signed with the QR
    secret (HS256). It is *static* — no ``exp`` claim, so the QR under an event can
    be printed once and reused all session (rotation/expiry is US-9, deferred).
    Signing means a student cannot forge a code for a task they cannot see.
    """
    payload = {"task_id": task_id, "typ": _TYP}
    return jwt.encode(payload, get_settings().qr_secret, algorithm=_ALG)


def verify_event_token(token: str) -> int | None:
    """Return the token's ``task_id``, or ``None`` if missing/tampered/wrong-type."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, get_settings().qr_secret, algorithms=[_ALG])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != _TYP:
        return None
    task_id = payload.get("task_id")
    return task_id if isinstance(task_id, int) else None
