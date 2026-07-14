from __future__ import annotations

from functools import lru_cache

from app.auth.provider import AuthProvider
from app.config import get_settings


@lru_cache
def get_auth_provider() -> AuthProvider:
    """Select the IdP implementation from config. Default: mock (demo)."""
    provider = get_settings().auth_provider.lower()
    if provider == "mock":
        from app.auth.mock_idp import MockIdp

        return MockIdp()
    if provider == "saml":
        # SamlProvider needs real SP/IdP settings; supply them here when wiring a
        # campus IdP. Importing it does NOT import xmlsec (that stays lazy).
        from app.auth.saml_provider import SamlProvider

        return SamlProvider(settings={})
    raise ValueError(
        f"Unknown WP_AUTH_PROVIDER: {provider!r} (expected 'mock' or 'saml')"
    )
