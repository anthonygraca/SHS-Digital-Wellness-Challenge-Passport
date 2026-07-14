from __future__ import annotations

from functools import lru_cache
from typing import Dict

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration. All values are overridable via environment variables."""

    model_config = SettingsConfigDict(env_prefix="WP_", env_file=".env", extra="ignore")

    # Which identity provider to use. "mock" (default, demo) or "saml" (real campus IdP).
    auth_provider: str = "mock"

    # Persistence. SQLite on disk for local dev/demo.
    database_url: str = "sqlite:///./wellness_passport.db"

    # Session signing (HS256). Override in any real deployment.
    jwt_secret: str = "dev-only-change-me-please-set-a-real-32B+-secret"
    jwt_ttl_seconds: int = 3600
    session_cookie: str = "wp_session"

    # SAML issuer -> campus_id. An unknown issuer is a failed auth, never a silent default.
    # Override via WP_CAMPUS_ISSUER_MAP as a JSON object string (pydantic-settings decodes it).
    campus_issuer_map: Dict[str, str] = {
        "mock-idp": "csub",
        "https://idp.csub.edu/idp/shibboleth": "csub",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
