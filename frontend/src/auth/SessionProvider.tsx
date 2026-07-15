import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { Session } from "../types/session";
import { fetchSession, logout as apiLogout } from "./auth";
import {
  clearOfflineSnapshot,
  readSessionSnapshot,
  writeSessionSnapshot,
} from "../offline/snapshot";

interface SessionContextValue {
  session: Session | null;
  loading: boolean;
  refresh: () => Promise<Session | null>;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    let next: Session | null = null;
    try {
      next = await fetchSession();
      // The server is the authority on who is signed in, so its answer is what we
      // cache — and a "no" clears the cache rather than being ignored. That is what
      // keeps the offline fallback below from ever resurrecting an ended session.
      if (next) writeSessionSnapshot(next);
      else clearOfflineSnapshot();
    } catch {
      // Offline, or the server is unreachable. fetch *rejects* here rather than
      // resolving with !res.ok, so fetchSession's own null-on-failure guard never
      // runs. Without this catch the rejection escapes refresh(), setLoading(false)
      // never runs, and every screen sits on "Loading…" forever instead of failing.
      //
      // Falling back to the last known session is what lets the passport render its
      // cached progress (US-6 / FR-C4) instead of bouncing to sign-in — which we
      // could not complete offline anyway, SAML being a redirect to the IdP.
      next = readSessionSnapshot();
    }
    setSession(next);
    setLoading(false);
    return next;
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
    setSession(null);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <SessionContext.Provider value={{ session, loading, refresh, signOut }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}
