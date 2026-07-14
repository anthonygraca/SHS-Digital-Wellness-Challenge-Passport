import { useSession } from "../../auth/SessionProvider";
import styles from "./NoActiveChallenge.module.css";

/**
 * Shown to an eligible student whose campus has no published challenge to join
 * (US-3 / FR-C1, scenario 3). Deliberately offers no enrollment action — there is
 * nothing to enroll in.
 */
export function NoActiveChallenge() {
  const { signOut } = useSession();

  return (
    <main className={styles.center}>
      <div className={styles.card}>
        <h1 className={styles.heading}>No active challenge</h1>
        <p className={styles.body}>
          There's no active challenge for your campus right now. Check back soon!
        </p>
        <button type="button" className={styles.signout} onClick={() => void signOut()}>
          Sign out
        </button>
      </div>
    </main>
  );
}
