import type { Session } from "../types/session";

/**
 * Whether the session belongs to campus staff / an admin (US-11).
 *
 * One definition, deliberately: `AdminRoute` sends non-admins from /admin to
 * /home, and the landing sends admins from /home to /admin. If those two ever
 * disagreed about who is an admin, the two redirects would bounce a user back
 * and forth forever.
 *
 * Substring match, unlike `isCurrentStudent` (which is an exact match on
 * "student" so that "non-student" cannot slip through). Affiliation here is a
 * free-form IdP string, and admin access is not a participation-eligibility
 * decision — it only decides which home screen you land on, and /admin is
 * guarded server-side by `require_admin`.
 */
export function isAdminSession(session: Session): boolean {
  const affiliation = session.affiliation.toLowerCase();
  return affiliation.includes("admin") || affiliation.includes("staff");
}
