import { Navigate } from "react-router-dom";
import { useSession } from "../../auth/SessionProvider";
import styles from "./Landing.module.css";

/**
 * Minimal authenticated landing for US-1: confirms the session is live. The real
 * passport (US-5) replaces this later. Guards against being viewed signed-out.
 */
export function Landing() {
  const { session, loading, signOut } = useSession();

  if (loading) return <div className={styles.center}>Loading…</div>;
  if (!session) return <Navigate to="/" replace />;

  return (
    <main className={styles.center}>
      <div className={styles.card}>
        <h1 className={styles.heading}>You're signed in</h1>
        <p className={styles.line}>
          Signed in as <strong>{session.affiliation}</strong>
        </p>
        <p className={styles.subject}>{session.subject}</p>
        <button type="button" className={styles.signout} onClick={() => void signOut()}>
          Sign out
        </button>
      </div>
    </main>
  );
}
