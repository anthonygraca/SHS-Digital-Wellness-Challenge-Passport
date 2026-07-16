from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.auth.deps import current_claims
from app.auth.eligibility import is_current_student
from app.auth.provider import AuthError, AuthProvider
from app.auth.registry import get_auth_provider
from app.auth.session import mint_session_token
from app.config import get_settings
from app.repositories.base import Repository, get_repo
from app.schemas.session import SessionOut
from app.services.campus import campus_id_for_issuer

router = APIRouter()


def _with_status(return_to: str, status_value: str) -> str:
    sep = "&" if "?" in return_to else "?"
    return f"{return_to}{sep}{urlencode({'status': status_value})}"


@router.get("/auth/login")
def login(returnTo: str = "/", provider: AuthProvider = Depends(get_auth_provider)):
    """SP-initiated sign-in: hand the browser to the IdP (mock or real)."""
    return RedirectResponse(
        provider.build_login_redirect(returnTo), status_code=status.HTTP_302_FOUND
    )


@router.post("/auth/acs")
async def acs(
    request: Request,
    provider: AuthProvider = Depends(get_auth_provider),
    repo: Repository = Depends(get_repo),
):
    """Assertion Consumer Service: validate the IdP callback and open a session.

    Failed/invalid assertions redirect back with status=failed and write nothing.
    """
    form = await request.form()
    return_to = form.get("returnTo") or "/"

    try:
        assertion = await provider.consume(request)
        campus_id = campus_id_for_issuer(assertion.issuer)
    except AuthError:
        # No session, no DB write — the third Gherkin scenario.
        return RedirectResponse(
            _with_status(return_to, "failed"), status_code=status.HTTP_302_FOUND
        )

    student = repo.get_or_create_student(
        campus_id=campus_id,
        sso_subject=assertion.sso_subject,
        affiliation=assertion.affiliation,
    )

    token = mint_session_token(
        sso_subject=assertion.sso_subject,
        affiliation=assertion.affiliation,
        campus_id=campus_id,
        student_id=student.id,
    )
    settings = get_settings()
    response = RedirectResponse(return_to, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        settings.session_cookie,
        token,
        max_age=settings.jwt_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return response


@router.get("/auth/session", response_model=SessionOut)
def session(request: Request):
    """Return the current session for the SPA, or 401 if not signed in."""
    claims = current_claims(request)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in"
        )
    affiliation = claims.get("affiliation", "")
    return SessionOut(
        subject=claims["sub"],
        affiliation=affiliation,
        isCurrentStudent=is_current_student(affiliation),
    )


@router.post("/auth/logout")
def logout():
    """Clear the session cookie."""
    response = JSONResponse({"ok": True})
    response.delete_cookie(get_settings().session_cookie, path="/")
    return response


@router.get("/mock-idp/login", response_class=HTMLResponse)
def mock_idp_login(returnTo: str = "/"):
    """Dev-only fake IdP login page. Available only when AUTH_PROVIDER=mock.

    Lets a tester pick a subject/affiliation or force a failed assertion, then
    POSTs those "assertion" fields to the ACS — standing in for a real campus IdP.
    """
    if get_settings().auth_provider.lower() != "mock":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _MOCK_IDP_PAGE.replace("__RETURN_TO__", _html_escape(returnTo))


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


_MOCK_IDP_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Mock Campus IdP</title>
  <style>
    body {
      font-family: system-ui, sans-serif;
      background: #10141c; color: #e8eaed;
      display: grid; place-items: center;
      min-height: 100vh; margin: 0;
    }
    form {
      background: #1b2230; padding: 28px;
      border-radius: 16px; width: 320px;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
    }
    h1 { font-size: 18px; margin: 0 0 4px; }
    p.sub { margin: 0 0 16px; color: #9aa0a6; font-size: 13px; }
    .presets { display: flex; gap: 8px; margin-bottom: 16px; }
    .preset {
      flex: 1; padding: 8px 0; border-radius: 8px; border: 1px solid #3c4043;
      background: #10141c; color: #e8eaed; font-size: 12px;
      cursor: pointer; text-align: center;
    }
    .preset:hover { border-color: #b3261e; color: #ff4438; }
    label { display: block; font-size: 13px; margin: 14px 0 6px; }
    input[type="text"] {
      width: 100%; box-sizing: border-box; padding: 10px;
      border-radius: 8px; border: 1px solid #3c4043;
      background: #10141c; color: #fff;
    }
    .row {
      display: flex; align-items: center;
      gap: 8px; margin-top: 16px; font-size: 13px;
    }
    button[type="submit"] {
      width: 100%; margin-top: 20px; padding: 12px;
      border: none; border-radius: 24px; background: #b3261e;
      color: #fff; font-weight: 600; font-size: 14px; cursor: pointer;
    }
  </style>
</head>
<body>
  <form method="post" action="/auth/acs">
    <h1>Mock Campus IdP</h1>
    <p class="sub">Dev stand-in for campus SAML SSO. Not shown in production.</p>
    <div class="presets">
      <button type="button" class="preset"
        onclick="document.getElementById('subject').value='student@csub.edu';
                 document.getElementById('affiliation').value='student'">
        Student
      </button>
      <button type="button" class="preset"
        onclick="document.getElementById('subject').value='staff@csub.edu';
                 document.getElementById('affiliation').value='staff'">
        Staff&nbsp;(admin)
      </button>
    </div>
    <input type="hidden" name="returnTo" value="__RETURN_TO__" />
    <label for="subject">SSO subject (eduPersonPrincipalName)</label>
    <input id="subject" type="text" name="subject" value="abc@csub.edu" />
    <label for="affiliation">Affiliation</label>
    <input id="affiliation" type="text" name="affiliation" value="student" />
    <div class="row">
      <input id="fail" type="checkbox" name="fail" value="1" />
      <label for="fail" style="margin:0">Force a failed assertion</label>
    </div>
    <button type="submit">Authenticate</button>
  </form>
</body>
</html>
"""
