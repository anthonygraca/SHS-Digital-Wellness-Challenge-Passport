from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request

from app.auth.provider import AssertionResult, AuthError

# Fixed issuer for the mock IdP; maps to a campus via config.campus_issuer_map.
MOCK_ISSUER = "mock-idp"


class MockIdp:
    """A pure-Python stand-in for a campus SAML IdP (demo default).

    No xmlsec, no network. It hands the browser to an in-app dev login page
    (GET /mock-idp/login), which POSTs the "assertion" fields back to the ACS.
    The real seam (build_login_redirect / consume) is identical to SamlProvider,
    so swapping AUTH_PROVIDER=saml changes nothing outside app/auth.
    """

    def build_login_redirect(self, return_to: str) -> str:
        return "/mock-idp/login?" + urlencode({"returnTo": return_to})

    async def consume(self, request: Request) -> AssertionResult:
        form = await request.form()

        # Simulates the IdP returning a failed/invalid assertion.
        if form.get("fail"):
            raise AuthError("Mock IdP: authentication failed")

        subject = (form.get("subject") or "").strip()
        if not subject:
            raise AuthError("Mock IdP: assertion missing subject")

        affiliation = (form.get("affiliation") or "student").strip()
        return AssertionResult(
            sso_subject=subject, affiliation=affiliation, issuer=MOCK_ISSUER
        )
