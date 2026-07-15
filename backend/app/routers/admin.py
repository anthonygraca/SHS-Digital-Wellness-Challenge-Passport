"""Admin-only endpoints (US-4, FR-A4).

Demonstrates role-based access control for admin surfaces like challenge
builder and reports.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.rbac import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/challenges")
def list_challenges(claims: dict = Depends(require_admin)):
    """List all challenges (admin only).

    This is a placeholder endpoint to demonstrate RBAC (US-4). Students
    attempting to access this will receive 403 Forbidden.
    """
    return {
        "message": "Admin access granted",
        "admin_subject": claims["sub"],
        "challenges": [],
    }


@router.get("/reports")
def get_reports(claims: dict = Depends(require_admin)):
    """Access reports dashboard (admin only).

    Placeholder for US-21 (participation & completion funnel report).
    """
    return {
        "message": "Admin reports access granted",
        "admin_subject": claims["sub"],
    }
