import { startLogin } from "../../auth/auth";
import styles from "./AuthError.module.css";

/**
 * Failed-auth retry prompt (US-1 Gherkin scenario 3). Reached when the IdP
 * returns an invalid/failed assertion — backend created no record.
 */
export function AuthError() {
  return (
    <main className={styles.center}>
      <div className={styles.card}>
        <h1 className={styles.heading}>Sign-in didn't complete</h1>
        <p className={styles.body}>
          We couldn't verify your campus sign-in. No account was created. Please try
          again.
        </p>
        <button type="button" className={styles.retry} onClick={startLogin}>
          Try again
        </button>
      </div>
    </main>
  );
}
