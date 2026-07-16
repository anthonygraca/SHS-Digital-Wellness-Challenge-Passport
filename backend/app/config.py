from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored to backend/ (parent of this app/ package) so the DB file resolves to the
# same path regardless of the process's cwd — e.g. `cd backend && uvicorn ...` vs.
# `uvicorn --app-dir backend ...` from the repo root previously produced two different
# on-disk databases for a relative "./wellness_passport.db" path.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_DB_PATH = _BACKEND_DIR / "wellness_passport.db"


class Settings(BaseSettings):
    """App configuration. All values are overridable via environment variables."""

    model_config = SettingsConfigDict(env_prefix="WP_", env_file=".env", extra="ignore")

    # Which identity provider to use. "mock" (default, demo) or "saml" (real campus IdP).
    auth_provider: str = "mock"

    # Which persistence backend to use:
    #   "sql"    — SQLAlchemy/SQLite (local dev + the pytest suite). Default.
    #   "dynamo" — DynamoDB via boto3 (AWS Lambda). Selected by WP_PERSISTENCE=dynamo.
    persistence: str = "sql"

    # Persistence. SQLite on disk for local dev/demo.
    database_url: str = f"sqlite:///{_DEFAULT_DB_PATH}"

    # DynamoDB (persistence="dynamo"). Table names are `{prefix}{Entity}` so SAM can
    # own the real names and the per-function IAM policies can scope to them, e.g.
    # "wp-Students", "wp-Challenges", … . aws_region/endpoint_url let DynamoDB Local
    # (http://localhost:8000) be targeted for offline testing; both default to the
    # boto3/AWS environment when unset.
    ddb_table_prefix: str = "wp-"
    aws_region: str | None = None
    ddb_endpoint_url: str | None = None

    # Session cookie is marked Secure when served over HTTPS (behind CloudFront in
    # production). Left False for local plain-HTTP dev so the cookie still sets.
    cookie_secure: bool = False

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
