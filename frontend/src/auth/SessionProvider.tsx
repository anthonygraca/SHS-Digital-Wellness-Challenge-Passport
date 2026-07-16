import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { Bootstrap } from "../types/bootstrap";
import type { EnrollmentStatus } from "../types/enrollment";
import type { Passport } from "../types/passport";
import type { Session } from "../types/session";
import { logout as apiLogout } from "./auth";
import { fetchBootstrap } from "../api/bootstrap";
import {
  clearOfflineSnapshot,
  readSessionSnapshot,
  writePassportSnapshot,
  writeSessionSnapshot,
} from "../offline/snapshot";

interface SessionContextValue {
  session: Session | null;
  /**
   * The enrollment and passport answers that arrived with the session, for the
   * screens that used to fetch them one after another. Null means "no answer for
   * you" — not a participating student, not enrolled, or we never reached the
   * server — so a consumer that needs one must still be able to fetch it itself.
   */
  enrollment: EnrollmentStatus | null;
  passport: Passport | null;
  loading: boolean;
  refresh: () => Promise<Session | null>;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

const EMPTY: Bootstrap = { session: null, enrollment: null, passport: null };

/**
 * Holds the session, and seeds the first render from a single request.
 *
 * This provider used to fetch /auth/session alone, which started a waterfall: Landing
 * could not ask /enrollment until the session landed, and Passport could not ask
 * /api/passport until Landing had redirected. Three sequential hops, three Lambdas,
 * two of them rendering nothing while they waited. /api/bootstrap answers all three
 * at once, and the two extra answers are published here for whoever needs them.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [{ session, enrollment, passport }, setData] = useState<Bootstrap>(EMPTY);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    let next: Bootstrap;
    try {
      next = await fetchBootstrap();
      // The server is the authority on who is signed in, so its answer is what we
      // cache — and a "no" clears the cache rather than being ignored. That is what
      // keeps the offline fallback below from ever resurrecting an ended session.
      if (next.session) {
        writeSessionSnapshot(next.session);
        // The passport arrives with the session now, so the snapshot is written here
        // rather than by Passport's fetch — which no longer runs when this seeded it.
        // Only ever written, never cleared: a null passport means "not enrolled", not
        // "your progress is gone", and dropping a good snapshot over it would cost a
        // student their offline passport (US-6 / FR-C4).
        if (next.passport) writePassportSnapshot(next.passport);
      } else {
        clearOfflineSnapshot();
      }
    } catch {
      // Offline, or the server is unreachable. fetch *rejects* here rather than
      // resolving with !res.ok, so fetchBootstrap's own empty-on-failure guard never
      // runs. Without this catch the rejection escapes refresh(), setLoading(false)
      // never runs, and every screen sits on "Loading…" forever instead of failing.
      //
      // Falling back to the last known session is what lets the passport render its
      // cached progress (US-6 / FR-C4) instead of bouncing to sign-in — which we
      // could not complete offline anyway, SAML being a redirect to the IdP.
      //
      // Only the session is restored. The cached passport is deliberately left for
      // Passport to read, because reading it is how that screen knows to mark itself
      // stale and raise the offline banner; seeding it from here would hand it cached
      // data wearing a live face.
      next = { ...EMPTY, session: readSessionSnapshot() };
    }
    setData(next);
    setLoading(false);
    return next.session;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // Ignored on purpose. Offline, apiLogout rejects; without this the throw
      // would leave the user still signed in on what may well be a shared phone.
      // Clearing locally is the honest outcome either way — the server cookie
      // expires on its own, and there is no failure here worth showing a student
      // who has already been returned to the sign-in screen.
    }
    // Unconditional, and before the state update: signing out on a shared phone has
    // to take the cached passport with it, whether or not the server heard about it.
    clearOfflineSnapshot();
    setData(EMPTY);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <SessionContext.Provider
      value={{ session, enrollment, passport, loading, refresh, signOut }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}
