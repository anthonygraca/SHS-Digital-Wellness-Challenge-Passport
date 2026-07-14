import { Navigate } from "react-router-dom";
import { useSession } from "../../auth/SessionProvider";
import { EligibilityBlocked } from "../EligibilityBlocked/EligibilityBlocked";
import styles from "./Landing.module.css";

/**
 * Minimal authenticated landing for US-1: confirms the session is live. The real
 * passport (US-5) replaces this later. Guards against being viewed signed-out.
 *
 * US-2 (FR-A3): current-student eligibility gate. A non-current student is blocked
 * with a friendly message; a current student may proceed to join the challenge.
 */
export function Landing() {
  const { session, loading, signOut } = useSession();

  if (loading) return <div className={styles.center}>Loading…</div>;
  if (!session) return <Navigate to="/" replace />;
  if (!session.isCurrentStudent) return <EligibilityBlocked />;

  return (
    <main className={styles.center}>
      <div className={styles.card}>
        <h1 className={styles.heading}>You're signed in</h1>
        <p className={styles.line}>
          Signed in as <strong>{session.affiliation}</strong>
        </p>
        <p className={styles.subject}>{session.subject}</p>
        {/* TODO(US-3): wire this to POST /enrollment for the active challenge. */}
        <button type="button" className={styles.join} disabled>
          Join the Challenge
        </button>
        <button type="button" className={styles.signout} onClick={() => void signOut()}>
          Sign out
        </button>
      </div>
    </main>
  );
}
