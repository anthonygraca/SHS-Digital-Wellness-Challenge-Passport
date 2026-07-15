"""Role-based access control (RBAC) dependencies for FastAPI (FR-A4, US-4).

Provides require_role(), require_student(), and require_admin() dependencies
to protect endpoints based on the role claim in the session JWT.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.auth.deps import current_claims
from app.models.student import Role


def require_role(allowed_roles: set[Role]):
    """Dependency factory: require the session role to be in allowed_roles.

    Returns a FastAPI dependency that raises 401 if not authenticated or
    403 if authenticated but role is not allowed.

    Usage:
        @router.get("/admin/reports", dependencies=[Depends(require_role({Role.ADMIN}))])
    """

    def _check_role(request: Request) -> dict:
        claims = current_claims(request)
        if not claims:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        role = claims.get("role")
        if role not in {r.value for r in allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: insufficient permissions",
            )

        return claims

    return _check_role


def require_student(request: Request) -> dict:
    """Require student role. Returns session claims if authorized.

    Raises 401 if not authenticated, 403 if not a student role.

    Usage:
        @router.get("/api/passport")
        def get_passport(claims: dict = Depends(require_student)):
            student_id = claims["student_id"]
            ...
    """
    return require_role({Role.STUDENT})(request)


def require_admin(request: Request) -> dict:
    """Require admin role. Returns session claims if authorized.

    Raises 401 if not authenticated, 403 if not an admin role.

    Usage:
        @router.post("/api/admin/challenges")
        def create_challenge(claims: dict = Depends(require_admin)):
            ...
    """
    return require_role({Role.ADMIN})(request)


def require_any_authenticated(request: Request) -> dict:
    """Require any authenticated session (student or admin).

    Raises 401 if not authenticated. Returns session claims.

    Usage:
        @router.get("/api/profile")
        def get_profile(claims: dict = Depends(require_any_authenticated)):
            ...
    """
    claims = current_claims(request)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return claims
