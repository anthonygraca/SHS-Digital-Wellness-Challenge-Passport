import { startLogin } from "../../auth/auth";
import { useThemeCopy } from "../../theme/ThemeProvider";
import { LockIcon, SchoolIcon } from "../icons";
import { VersionStamp } from "../VersionStamp/VersionStamp";
import styles from "./SignIn.module.css";

/**
 * S1a — Campus SSO sign-in (US-1 / FR-A1, FR-A2).
 *
 * Exactly one action: "Sign in with campus SSO". There are deliberately NO
 * credential inputs — no ID field, no password. onSignIn is injectable so the
 * navigation can be spied on in tests.
 */
export function SignIn({ onSignIn = startLogin }: { onSignIn?: () => void }) {
  // Pre-auth, so no challenge theme is known yet: this shows the default skin's copy.
  const { appTitle, tagline } = useThemeCopy();

  return (
    <main className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.mark}>
          <SchoolIcon size={40} />
        </span>
        <h1 className={styles.title}>{appTitle}</h1>
        <p className={styles.tagline}>{tagline}</p>
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
        {/* Which build is deployed (#64). Sign-in is the one screen everyone
            lands on, and it is pre-auth, so it is reachable when diagnosing a
            deployment nobody can get into. Renders nothing unless stamped. */}
        <VersionStamp />
      </section>
    </main>
  );
}
