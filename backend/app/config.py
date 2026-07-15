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

    # AWS Bedrock for AI features (US-15, US-16, FR-E1, FR-E6)
    aws_region: str = "us-west-2"
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_max_tokens: int = 1024
    bedrock_temperature: float = 0.7

    # AI feature flags
    ai_tips_enabled: bool = True  # Enable personalized tips (US-15)
    conversation_guide_enabled: bool = True  # Enable conversation guide (US-16)

    # Conversation guide settings (US-16)
    max_conversation_history: int = 20  # Max messages to include in context

    # Theme personas for conversation guide (US-16)
    theme_personas: dict[str, str] = {
        "default": "You are a supportive wellness guide for CSUB students.",
        "Stranger Things": "You are a wellness guide with an adventurous, mysterious tone inspired by Stranger Things. Stay supportive and informative while adding subtle references to discovery and overcoming challenges.",
    }

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
