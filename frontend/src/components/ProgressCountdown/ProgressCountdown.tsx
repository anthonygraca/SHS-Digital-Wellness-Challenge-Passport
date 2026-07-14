import type { Progress } from "../../types/challenge";
import styles from "./ProgressCountdown.module.css";

interface ProgressCountdownProps {
  progress: Progress;
}

/**
 * ProgressCountdown component (US-5, FR-C3): displays progress summary.
 *
 * Format: "X of Y complete, Z remaining"
 * Example: "3 of 7 complete, 4 remaining"
 */
export function ProgressCountdown({ progress }: ProgressCountdownProps) {
  const { completed, total_weeks, remaining } = progress;

  return (
    <div className={styles.container}>
      <div className={styles.progressBar}>
        <div
          className={styles.progressFill}
          style={{ width: `${(completed / total_weeks) * 100}%` }}
        />
      </div>
      <p className={styles.text}>
        <strong className={styles.completed}>{completed}</strong> of{" "}
        <strong className={styles.total}>{total_weeks}</strong> complete,{" "}
        <strong className={styles.remaining}>{remaining}</strong> remaining
      </p>
    </div>
  );
}
