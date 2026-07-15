import { useSession } from "../../auth/SessionProvider";
import styles from "./EligibilityBlocked.module.css";

/**
 * Current-student eligibility gate block (US-2 / FR-A3). Shown to a signed-in
 * user whose IdP affiliation is not "current student" — participation is limited
 * to current students, so there is nothing to enroll in here.
 */
export function EligibilityBlocked() {
  const { signOut } = useSession();

  return (
    <main className={styles.center}>
      <div className={styles.card}>
        <h1 className={styles.heading}>You're not eligible to join</h1>
        <p className={styles.body}>
          Participation is limited to current students. If you believe this is a
          mistake, please contact Student Health Services.
        </p>
        <button type="button" className={styles.signout} onClick={() => void signOut()}>
          Sign out
        </button>
      </div>
    </main>
  );
}
