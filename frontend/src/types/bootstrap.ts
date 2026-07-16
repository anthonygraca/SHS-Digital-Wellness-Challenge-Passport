import type { EnrollmentStatus } from "./enrollment";
import type { Passport } from "./passport";
import type { Session } from "./session";

/**
 * Everything the first render needs, in one response (GET /api/bootstrap).
 *
 * Each field is null-as-an-answer, never null-as-an-error — see the route's docstring
 * (backend/app/routers/bootstrap.py). `session: null` is "not signed in";
 * `enrollment: null` is "not a participating student" (staff, or ineligible);
 * `passport: null` is "not enrolled, so there is nothing to show yet".
 */
export interface Bootstrap {
  session: Session | null;
  enrollment: EnrollmentStatus | null;
  passport: Passport | null;
}
