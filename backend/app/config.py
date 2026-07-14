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

    # SAML issuer -> campus_id. An unknown issuer is a failed auth, not a default.
    # Override via WP_CAMPUS_ISSUER_MAP as JSON (pydantic-settings decodes it).
    campus_issuer_map: dict[str, str] = {
        "mock-idp": "csub",
        "https://idp.csub.edu/idp/shibboleth": "csub",
    }

    # AWS Bedrock for AI features (US-15, US-16, FR-E1, FR-E6)
    aws_region: str = "us-west-2"
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_max_tokens: int = 1024
    bedrock_temperature: float = 0.7

    # AI feature flags
    ai_tips_enabled: bool = True  # Enable personalized tips (US-15)

    # SHS content grounding (US-15, FR-E1, FR-E6)
    # In production, this would be a vector database or S3 reference
    # For MVP, we use inline wellness content
    shs_content_corpus: str = """
SHS-approved wellness content for grounding AI responses:

VISION HEALTH:
- Get your eyes checked annually, especially if you use screens frequently
- Follow the 20-20-20 rule: Every 20 minutes, look at something 20 feet away for 20 seconds
- Campus Health Services offers vision screening during wellness weeks
- Protect your eyes with UV-blocking sunglasses outdoors

NUTRITION:
- Balanced meals include proteins, whole grains, fruits, and vegetables
- Stay hydrated: aim for 8 glasses of water daily
- Campus dining offers healthy meal options - look for the "Balanced U" labels
- Limit processed foods and added sugars

PHYSICAL ACTIVITY:
- Aim for 150 minutes of moderate exercise weekly
- Campus Recreation Center offers free fitness classes for students
- Walking between classes counts as physical activity
- Find activities you enjoy to make fitness sustainable

MENTAL HEALTH:
- Stress is normal, but chronic stress needs attention
- Campus Counseling offers free confidential support
- Practice mindfulness: even 5 minutes of deep breathing helps
- Connect with peers through campus wellness programs

SLEEP HYGIENE:
- Aim for 7-9 hours nightly
- Keep a consistent sleep schedule, even on weekends
- Avoid screens 1 hour before bed
- Create a relaxing bedtime routine

PREVENTIVE CARE:
- Annual wellness check-ups detect issues early
- Stay up to date with vaccinations
- Know your family health history
- Student Health Services offers free or low-cost preventive services

CRISIS RESOURCES:
- National Suicide Prevention Lifeline: 988
- Campus Counseling 24/7 Crisis Line: (661) 654-3360
- Campus Police (emergency): (661) 654-2111
- Student Health Services front desk: (661) 654-3277
"""


@lru_cache
def get_settings() -> Settings:
    return Settings()
