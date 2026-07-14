import { Navigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useSession } from "../../auth/SessionProvider";
import { fetchPassport } from "../../api/passport";
import type { Passport } from "../../types/challenge";
import { WeekTile } from "../WeekTile/WeekTile";
import { ProgressCountdown } from "../ProgressCountdown/ProgressCountdown";
import styles from "./PassportView.module.css";

/**
 * PassportView component (US-5): displays student's challenge passport.
 *
 * Shows:
 * - Challenge name and theme
 * - Progress countdown ("X of Y complete, Z remaining")
 * - Week tiles in a responsive grid with status indicators
 * - Prize eligibility status
 */
export function PassportView() {
  const { session, loading: sessionLoading, signOut } = useSession();
  const [passport, setPassport] = useState<Passport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;

    let mounted = true;

    async function loadPassport() {
      try {
        const data = await fetchPassport();
        if (mounted) {
          setPassport(data);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to load passport");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void loadPassport();

    return () => {
      mounted = false;
    };
  }, [session]);

  // Redirect to sign-in if not authenticated
  if (sessionLoading) {
    return <div className={styles.loading}>Loading session…</div>;
  }

  if (!session) {
    return <Navigate to="/" replace />;
  }

  // Loading passport data
  if (loading) {
    return <div className={styles.loading}>Loading your passport…</div>;
  }

  // Error state
  if (error || !passport) {
    return (
      <div className={styles.error}>
        <div className={styles.errorCard}>
          <h2 className={styles.errorHeading}>Unable to load passport</h2>
          <p className={styles.errorMessage}>
            {error || "No active challenge found"}
          </p>
          <button
            type="button"
            className={styles.signoutButton}
            onClick={() => void signOut()}
          >
            Sign out
          </button>
        </div>
      </div>
    );
  }

  return (
    <main className={styles.container}>
      <header className={styles.header}>
        <div className={styles.headerContent}>
          <h1 className={styles.challengeName}>{passport.challenge.name}</h1>
          {passport.challenge.theme_name && (
            <p className={styles.themeName}>{passport.challenge.theme_name}</p>
          )}
          <ProgressCountdown progress={passport.progress} />
        </div>
        <button
          type="button"
          className={styles.signoutButton}
          onClick={() => void signOut()}
          aria-label="Sign out"
        >
          Sign out
        </button>
      </header>

      <section className={styles.weeksSection}>
        <div className={styles.weeksGrid}>
          {passport.tasks.map((task) => (
            <WeekTile key={task.id} task={task} />
          ))}
        </div>
      </section>

      {passport.progress.is_prize_eligible && (
        <aside className={styles.prizeNotice}>
          <span className={styles.prizeIcon}>🎉</span>
          <span className={styles.prizeText}>
            You're eligible for the prize drawing!
          </span>
        </aside>
      )}
    </main>
  );
}
