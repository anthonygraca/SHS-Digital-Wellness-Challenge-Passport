from __future__ import annotations

from app.auth.provider import AuthError
from app.config import get_settings


def campus_id_for_issuer(issuer: str) -> str:
    """Map a SAML issuer to a campus_id (multi-tenancy seam, FR-A5).

    An unknown issuer is treated as a failed authentication rather than being
    assigned to a silent default campus.
    """
    campus_id = get_settings().campus_issuer_map.get(issuer)
    if not campus_id:
        raise AuthError(f"Unknown SAML issuer: {issuer!r}")
    return campus_id
