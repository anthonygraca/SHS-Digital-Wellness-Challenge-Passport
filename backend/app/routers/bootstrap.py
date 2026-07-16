from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth.deps import current_claims
from app.auth.eligibility import is_current_student
from app.repositories.base import Repository, get_repo
from app.routers.passport import to_passport_out
from app.schemas.bootstrap import BootstrapOut
from app.schemas.enrollment import ActiveChallenge, EnrollmentStatusOut
from app.schemas.session import SessionOut

router = APIRouter()


@router.get("/api/bootstrap", response_model=BootstrapOut)
def bootstrap(
    request: Request,
    repo: Repository = Depends(get_repo),
):
    """Everything the SPA's first render needs, in one round trip.

    The app opened on three sequential fetches — ``/auth/session``, then
    ``/enrollment``, then ``/api/passport`` — each waiting on the one before to know
    whether it should even run, each its own Lambda with its own cold-start risk, and
    the first two rendering nothing while they waited. The data does not actually have
    that dependency: one request holding the session claims can resolve all three.

    Deliberately **not** gated on ``require_current_student``. Every other student
    route 401s or 403s an unauthorized caller, which is right when the caller asked
    for a student's data. This route asks "what am I?", and every honest answer to
    that — signed out, staff, ineligible — is a 200 with nulls. Making it 401 would
    put a failed request on the sign-in path of every first-time visitor, and hand the
    SPA an error to branch on where it wants a value.

    The eligibility gate still holds where it matters: the passport is only ever built
    for a current student, and ``/api/passport`` enforces it independently for anyone
    who asks that route directly.
    """
    claims = current_claims(request)
    if claims is None:
        return BootstrapOut()

    affiliation = claims.get("affiliation", "")
    session = SessionOut(
        subject=claims["sub"],
        affiliation=affiliation,
        isCurrentStudent=is_current_student(affiliation),
    )
    # Staff and ineligible students have no enrollment question to answer — the SPA
    # sends the first to the admin builder and the second to EligibilityBlocked.
    if not session.isCurrentStudent:
        return BootstrapOut(session=session)

    challenge = repo.get_active_challenge(claims["campus_id"])
    if challenge is None:
        return BootstrapOut(
            session=session,
            enrollment=EnrollmentStatusOut(active_challenge=None, enrolled=False),
        )

    enrolled = repo.get_enrollment(claims["student_id"], challenge.id) is not None
    enrollment = EnrollmentStatusOut(
        active_challenge=ActiveChallenge.model_validate(challenge), enrolled=enrolled
    )
    if not enrolled:
        return BootstrapOut(session=session, enrollment=enrollment)

    # build_passport_for, not build_passport: the active challenge is already resolved
    # above for the enrollment answer, and re-resolving it is a wasted query on the
    # one request the whole app waits for.
    return BootstrapOut(
        session=session,
        enrollment=enrollment,
        passport=to_passport_out(
            repo.build_passport_for(challenge, claims["student_id"])
        ),
    )
