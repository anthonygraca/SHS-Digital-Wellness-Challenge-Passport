from __future__ import annotations

from pydantic import BaseModel

from app.schemas.enrollment import EnrollmentStatusOut
from app.schemas.passport import PassportOut
from app.schemas.session import SessionOut


class BootstrapOut(BaseModel):
    """Everything the SPA needs to render its first screen, in one response.

    The three sub-objects are exactly the payloads of ``/auth/session``,
    ``/enrollment`` and ``/api/passport`` — this route composes those answers rather
    than inventing a fourth shape, so the SPA can seed from it and then revalidate
    against the individual routes with no translation.

    **Every field is nullable, and each null is a real answer rather than an error.**
    That is the whole design: a signed-out visitor gets 200 with three nulls, not a
    401, so the SPA renders sign-in without a failed request in the console — and one
    response can drive every branch the app currently spreads across three sequential
    fetches.

    - ``session``: null when not signed in.
    - ``enrollment``: null when there is no student enrollment to speak of — an
      admin/staff session, or a non-current student blocked by the US-2 gate.
    - ``passport``: null unless the student is enrolled in an active challenge.
      Not an assertion that no passport could be built: ``/api/passport`` answers for
      an unenrolled student too. It means "you are not enrolled, so the SPA is about
      to show you Join, and building this would be work spent on a screen nobody sees".
    """

    session: SessionOut | None = None
    enrollment: EnrollmentStatusOut | None = None
    passport: PassportOut | None = None
