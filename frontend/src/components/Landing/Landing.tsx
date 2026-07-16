import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "../../auth/SessionProvider";
import { isAdminSession } from "../../auth/roles";
import { ApiError } from "../../api/challenges";
import { enroll, fetchEnrollmentStatus } from "../../api/enrollment";
import type { EnrollmentStatus } from "../../types/enrollment";
import { EligibilityBlocked } from "../EligibilityBlocked/EligibilityBlocked";
import { NoActiveChallenge } from "../NoActiveChallenge/NoActiveChallenge";
import { useThemeCopy } from "../../theme/ThemeProvider";
import styles from "./Landing.module.css";

/**
 * Minimal authenticated landing for US-1: confirms the session is live.
 *
 * This is the *student* landing. Staff/admins are redirected to the Challenge
 * Builder before any of it runs: the US-2 gate below is about eligibility to
 * *participate in a challenge*, not to use the app, so sending staff into it
 * would block them behind "not eligible to join" — the builder is their home.
 *
 * US-2 (FR-A3): current-student eligibility gate. A non-current student is blocked
 * with a friendly message; a current student may proceed to join the challenge.
 *
 * US-3 (FR-C1): challenge enrollment. Once past the gate we ask the server what's
 * joinable and branch: no active challenge for the campus → friendly message with
 * no enroll action; already enrolled → straight to the passport; otherwise offer
 * the Join CTA, which enrolls and lands on the passport.
 */
export function Landing() {
  const { session, enrollment, loading, signOut } = useSession();
  // Themed copy (US-13). The palette lands once the passport is fetched, so this
  // pre-enrollment screen shows the default skin's title.
  const { appTitle } = useThemeCopy();
  // Seeded from the bootstrap payload, which answered the enrollment question in the
  // same request that established the session. Local state because Join mutates it.
  const [status, setStatus] = useState<EnrollmentStatus | null>(enrollment);
  const [statusLoading, setStatusLoading] = useState(enrollment == null);
  const [statusFailed, setStatusFailed] = useState(false);
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  // Only eligible students have an enrollment to look up; everyone else is
  // short-circuited by a guard below before statusLoading is ever read.
  const isEligible = Boolean(session?.isCurrentStudent);

  const loadStatus = useCallback(() => {
    setStatusLoading(true);
    setStatusFailed(false);
    return fetchEnrollmentStatus()
      .then((next) => ({ ok: true as const, next }))
      .catch(() => ({ ok: false as const, next: null }));
  }, []);

  useEffect(() => {
    if (!isEligible) return;
    // Bootstrap already answered this. Fetching again would re-introduce, at the cost
    // of a round trip, exactly the hop this screen was changed to stop making.
    if (enrollment) {
      setStatus(enrollment);
      setStatusLoading(false);
      return;
    }
    // No seed: the provider is offline, or an eligible student arrived without one.
    // The fetch stays as the fallback so this screen can still answer for itself.
    let cancelled = false;
    void loadStatus().then((res) => {
      if (cancelled) return;
      if (res.ok) setStatus(res.next);
      else setStatusFailed(true);
      setStatusLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [isEligible, enrollment, loadStatus]);

  const handleJoin = useCallback(async () => {
    setJoining(true);
    setJoinError(null);
    try {
      await enroll();
      // Flipping enrolled re-renders into the passport redirect below — the same
      // path a returning, already-enrolled student takes.
      setStatus((prev) => (prev ? { ...prev, enrolled: true } : prev));
    } catch (err) {
      setJoinError(
        err instanceof ApiError
          ? err.message
          : "We couldn't sign you up just now. Please try again.",
      );
    } finally {
      setJoining(false);
    }
  }, []);

  if (loading) return <div className={styles.center}>Loading…</div>;
  if (!session) return <Navigate to="/" replace />;
  // Before the student gate: staff are not ineligible participants, they are a
  // different persona. AdminRoute guards the destination.
  if (isAdminSession(session)) return <Navigate to="/admin" replace />;
  if (!session.isCurrentStudent) return <EligibilityBlocked />;
  if (statusLoading) return <div className={styles.center}>Loading…</div>;

  // A failed lookup is not the same as "no challenge" — don't imply the campus has
  // nothing running when we simply couldn't ask.
  if (statusFailed) {
    return (
      <main className={styles.center}>
        <div className={styles.card}>
          <h1 className={styles.heading}>Something went wrong</h1>
          <p className={styles.subject}>
            We couldn't load your challenge. Please try again.
          </p>
          <button
            type="button"
            className={styles.join}
            onClick={() => {
              void loadStatus().then((res) => {
                if (res.ok) setStatus(res.next);
                else setStatusFailed(true);
                setStatusLoading(false);
              });
            }}
          >
            Retry
          </button>
          <button type="button" className={styles.signout} onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </main>
    );
  }

  if (!status?.active_challenge) return <NoActiveChallenge />;
  if (status.enrolled) return <Navigate to="/passport" replace />;

  return (
    <main className={styles.center}>
      <div className={styles.card}>
        <p className={styles.appTitle}>{appTitle}</p>
        <h1 className={styles.heading}>You're signed in</h1>
        <p className={styles.line}>
          Signed in as <strong>{session.affiliation}</strong>
        </p>
        <p className={styles.subject}>{session.subject}</p>
        <button
          type="button"
          className={styles.join}
          onClick={() => void handleJoin()}
          disabled={joining}
        >
          {joining ? "Joining…" : `Join the ${status.active_challenge.name}`}
        </button>
        {joinError && (
          <p className={styles.error} role="alert">
            {joinError}
          </p>
        )}
        <button type="button" className={styles.signout} onClick={() => void signOut()}>
          Sign out
        </button>
      </div>
    </main>
  );
}
