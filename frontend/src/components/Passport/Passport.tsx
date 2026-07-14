import { Navigate } from "react-router-dom";
import { useSession } from "../../auth/SessionProvider";
import styles from "./Passport.module.css";

/**
 * Placeholder passport (US-3 destination). Enrolling — or opening the app while
 * already enrolled — lands here. The real passport with weekly tasks, progress
 * and prize eligibility is US-5 (FR-C2/C5), which replaces this screen.
 */
export function Passport() {
  const { session, loading, signOut } = useSession();

  if (loading) return <div className={styles.center}>Loading…</div>;
  if (!session) return <Navigate to="/" replace />;

  return (
    <main className={styles.center}>
      <div className={styles.card}>
        <h1 className={styles.heading}>Your passport</h1>
        <p className={styles.body}>
          You're enrolled. Your weekly tasks will show up here.
        </p>
        <button type="button" className={styles.signout} onClick={() => void signOut()}>
          Sign out
        </button>
      </div>
    </main>
  );
}
