import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "../../auth/SessionProvider";
import { ApiError } from "../../api/challenges";
import { enroll, fetchEnrollmentStatus } from "../../api/enrollment";
import type { EnrollmentStatus } from "../../types/enrollment";
import { EligibilityBlocked } from "../EligibilityBlocked/EligibilityBlocked";
import { NoActiveChallenge } from "../NoActiveChallenge/NoActiveChallenge";
import styles from "./Landing.module.css";

/**
 * Minimal authenticated landing for US-1: confirms the session is live.
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
  const { session, loading, signOut } = useSession();
  const [status, setStatus] = useState<EnrollmentStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
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
  }, [isEligible, loadStatus]);

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

  const isAdmin =
    session.affiliation.toLowerCase().includes("admin") ||
    session.affiliation.toLowerCase().includes("staff");

  return (
    <main className={styles.center}>
      <div className={styles.card}>
        <h1 className={styles.heading}>You're signed in</h1>
        <p className={styles.line}>
          Signed in as <strong>{session.affiliation}</strong>
        </p>
        <p className={styles.subject}>{session.subject}</p>
        {isAdmin && (
          <a href="/admin" className={styles.adminLink}>
            Challenge Builder →
          </a>
        )}
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
