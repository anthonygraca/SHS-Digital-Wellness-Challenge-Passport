from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import require_admin
from app.repositories.base import Repository, get_repo
from app.schemas.theme import ThemeCreate, ThemeOut, ThemeUpdate

router = APIRouter(prefix="/api/themes", tags=["themes"])


def _get_theme_or_404(repo: Repository, theme_id: str):
    theme = repo.get_theme(theme_id)
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
    repo: Repository = Depends(get_repo),
):
    """Add a new re-skin preset."""
    if repo.get_theme(body.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Theme with this id already exists",
        )
    return repo.create_theme(body)


@router.get("", response_model=list[ThemeOut])
def list_themes(
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """List the themes an admin can apply to a challenge."""
    return repo.list_themes()


@router.get("/{theme_id}", response_model=ThemeOut)
def get_theme(
    theme_id: str,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Fetch a single theme's full configuration."""
    return _get_theme_or_404(repo, theme_id)


@router.patch("/{theme_id}", response_model=ThemeOut)
def update_theme(
    theme_id: str,
    body: ThemeUpdate,
    claims: dict = Depends(require_admin),
    repo: Repository = Depends(get_repo),
):
    """Edit a theme's palette, assets or copy — re-skins without a deploy (NFR-6)."""
    _get_theme_or_404(repo, theme_id)
    return repo.update_theme(theme_id, body)
