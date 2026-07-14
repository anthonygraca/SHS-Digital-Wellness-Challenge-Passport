import { startLogin } from "../../auth/auth";
import { ACTIVE_THEME, THEMES } from "../../theme/themes";
import { LockIcon, SchoolIcon } from "../icons";
import styles from "./SignIn.module.css";

/**
 * S1a — Campus SSO sign-in (US-1 / FR-A1, FR-A2).
 *
 * Exactly one action: "Sign in with campus SSO". There are deliberately NO
 * credential inputs — no ID field, no password. onSignIn is injectable so the
 * navigation can be spied on in tests.
 */
export function SignIn({ onSignIn = startLogin }: { onSignIn?: () => void }) {
  const theme = THEMES[ACTIVE_THEME];

  return (
    <main className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.mark}>
          <SchoolIcon size={40} />
        </span>
        <h1 className={styles.title}>{theme.appTitle}</h1>
        <p className={styles.tagline}>{theme.tagline}</p>
      </div>

      <section className={styles.sheet}>
        <button
          type="button"
          className={styles.cta}
          aria-label="Sign in with campus SSO"
          onClick={onSignIn}
        >
          <SchoolIcon size={20} />
          Sign in with campus SSO
        </button>

        <p className={styles.caption}>
          <LockIcon size={16} />
          SAML single sign-on · no ID number needed
        </p>
        <p className={styles.trace}>
          UC-1 · FR-A1 / FR-A2 — opaque SSO subject only, no PHI
        </p>
      </section>
    </main>
  );
}
