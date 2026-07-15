from __future__ import annotations

from functools import lru_cache

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

    # Event-QR signing (HS256), kept separate from the session secret so rotating
    # one never invalidates the other. Tokens are static per task (no expiry yet —
    # US-9 rotation is deferred). Override in any real deployment.
    qr_secret: str = "dev-only-change-me-please-set-a-real-qr-32B+-secret"

    # SAML issuer -> campus_id. An unknown issuer is a failed auth, not a default.
    # Override via WP_CAMPUS_ISSUER_MAP as JSON (pydantic-settings decodes it).
    campus_issuer_map: dict[str, str] = {
        "mock-idp": "csub",
        "https://idp.csub.edu/idp/shibboleth": "csub",
    }

    # Crisis routing for this campus (FR-E3 / NFR-8). Every per-campus deploy overrides
    # these via WP_* env (NFR-4) — see docker-compose.yml and scripts/deploy/provision.sh.
    #
    # PROVENANCE, and the reason this comment is long: these numbers are transcribed from
    # the design mock (docs/SHS Wellness Passport (standalone).html), which hard-codes
    # them in its crisis card. They are NOT yet confirmed by SHS — that is still open
    # question #6 in architecture-plan.md §11 ("exact campus counseling / SHS numbers to
    # hard-code") and #4 in requirements-and-use-cases.md. So they are defaults good
    # enough to dial in a demo and not yet good enough to rely on: a wrong number here is
    # worse than an obviously fake one, because a plausible one gets dialled by someone
    # who needed the right one. Confirm both with SHS before this reaches a student, and
    # delete this paragraph when they are signed off.
    #
    # 988 is not here. The Suicide & Crisis Lifeline is national, correct for every
    # campus, and the one number in this app that must not be misconfigurable — a
    # settings field for it is a field someone can typo into a dead number, and it buys
    # nothing back. It lives in services/guide_safety.py as a constant.
    campus_counseling_name: str = "CSUB Counseling"
    campus_counseling_phone: str = "(661) 654-3366"  # from the mock — pending SHS
    shs_front_desk_name: str = "SHS front desk"
    shs_front_desk_phone: str = "(661) 654-2394"  # from the mock — pending SHS


@lru_cache
def get_settings() -> Settings:
    return Settings()
