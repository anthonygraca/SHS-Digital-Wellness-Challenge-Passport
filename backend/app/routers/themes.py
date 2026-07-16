from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_admin
from app.db import get_db
from app.schemas.theme import ThemeCreate, ThemeOut, ThemeUpdate
from app.services import themes as svc

router = APIRouter(prefix="/api/themes", tags=["themes"])


def _get_theme_or_404(db: Session, theme_id: str):
    theme = svc.get_theme(db, theme_id)
    if theme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found"
        )
    return theme


# Themes are shared presets rather than per-campus rows, so these endpoints gate
# on require_admin without narrowing by claims["campus_id"] the way the challenge
# endpoints do. Students never call these — their resolved theme rides along on
# the passport response (US-13 / FR-B4).


@router.post("", response_model=ThemeOut, status_code=status.HTTP_201_CREATED)
def create_theme(
    body: ThemeCreate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Add a new re-skin preset."""
    if svc.get_theme(db, body.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Theme with this id already exists",
        )
    return svc.create_theme(db, body)


@router.get("", response_model=list[ThemeOut])
def list_themes(
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List the themes an admin can apply to a challenge."""
    return svc.list_themes(db)


@router.get("/{theme_id}", response_model=ThemeOut)
def get_theme(
    theme_id: str,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Fetch a single theme's full configuration."""
    return _get_theme_or_404(db, theme_id)


@router.patch("/{theme_id}", response_model=ThemeOut)
def update_theme(
    theme_id: str,
    body: ThemeUpdate,
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Edit a theme's palette, assets or copy — re-skins without a deploy (NFR-6)."""
    theme = _get_theme_or_404(db, theme_id)
    return svc.update_theme(db, theme, body)
