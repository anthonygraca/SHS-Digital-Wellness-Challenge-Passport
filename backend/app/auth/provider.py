from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from fastapi import Request


class AuthError(Exception):
    """Raised when an assertion is missing, invalid, or otherwise unusable.

    The auth router turns this into a failed sign-in (no session, no DB write).
    """


@dataclass(frozen=True)
class AssertionResult:
    """The minimal identity extracted from a validated IdP assertion (FR-A2).

    Nothing here is persisted beyond sso_subject + affiliation; issuer is used only
    to resolve the campus and is not stored.
    """

    sso_subject: str
    affiliation: str
    issuer: str


@runtime_checkable
class AuthProvider(Protocol):
    """The SAML seam. Everything outside app/auth is agnostic to mock vs. real."""

    def build_login_redirect(self, return_to: str) -> str:
        """Return the URL the browser should be redirected to, to begin sign-in."""
        ...

    async def consume(self, request: Request) -> AssertionResult:
        """Validate the IdP callback and return the asserted identity.

        Raises AuthError on any failed/invalid/absent assertion.
        """
        ...
