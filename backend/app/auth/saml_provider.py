from __future__ import annotations

from fastapi import Request

from app.auth.provider import AssertionResult, AuthError

# Attribute names commonly asserted by CSU Shibboleth IdPs.
_SUBJECT_ATTRS = ("eduPersonPrincipalName", "urn:oid:1.3.6.1.4.1.5923.1.1.1.6")
_AFFILIATION_ATTRS = ("eduPersonAffiliation", "urn:oid:1.3.6.1.4.1.5923.1.1.1.1")


class SamlProvider:
    """Real campus IdP via python3-saml (OneLogin).

    `onelogin.saml2` is imported lazily *inside* the methods so that merely
    importing this module (which the provider registry does at startup) never
    pulls the native xmlsec/libxmlsec1 dependency. It is only imported when
    AUTH_PROVIDER=saml actually exercises the flow — install with the [saml] extra.

    NOTE: This is the production seam, wired but not exercised in the demo. It
    needs SP/IdP settings (metadata, ACS URL, certs) supplied via python3-saml's
    settings before it can validate real assertions.
    """

    def __init__(self, settings: dict):
        self._settings = settings

    def _prepare(self, request: Request) -> dict:
        url = request.url
        return {
            "https": "on" if url.scheme == "https" else "off",
            "http_host": url.hostname or "",
            "server_port": str(url.port or ""),
            "script_name": url.path,
            "get_data": dict(request.query_params),
            "post_data": {},  # populated by the router before validation
        }

    def build_login_redirect(self, return_to: str) -> str:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth  # lazy: native dep

        auth = OneLogin_Saml2_Auth(
            {"https": "on", "http_host": "", "script_name": "", "get_data": {}, "post_data": {}},
            old_settings=self._settings,
        )
        return auth.login(return_to=return_to)

    async def consume(self, request: Request) -> AssertionResult:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth  # lazy: native dep

        form = await request.form()
        req = self._prepare(request)
        req["post_data"] = {k: v for k, v in form.items()}

        auth = OneLogin_Saml2_Auth(req, old_settings=self._settings)
        auth.process_response()
        if auth.get_errors() or not auth.is_authenticated():
            raise AuthError(auth.get_last_error_reason() or "SAML assertion invalid")

        attrs = auth.get_attributes()
        subject = _first(attrs, _SUBJECT_ATTRS) or auth.get_nameid()
        if not subject:
            raise AuthError("SAML assertion missing subject")
        affiliation = _first(attrs, _AFFILIATION_ATTRS) or "student"
        issuer = self._settings.get("idp", {}).get("entityId", "")
        return AssertionResult(sso_subject=subject, affiliation=affiliation, issuer=issuer)


def _first(attrs: dict, keys):
    for key in keys:
        values = attrs.get(key)
        if values:
            return values[0] if isinstance(values, (list, tuple)) else values
    return None
