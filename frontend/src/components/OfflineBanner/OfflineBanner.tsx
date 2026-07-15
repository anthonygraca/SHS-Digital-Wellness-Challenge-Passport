import { SensorsIcon } from "../icons";
import styles from "./OfflineBanner.module.css";

/**
 * Tells the student the progress they are looking at is not live (US-6 / FR-C4).
 *
 * Two distinct honest states, because they are not the same promise: `!online` is
 * "we know why this is stale", while `online && stale` is "we appear connected but
 * the refresh failed anyway" — the captive-portal case that navigator.onLine cannot
 * see. Saying "you're offline" in the second case would be a guess.
 *
 * role="status" rather than role="alert", matching the prize indicator: this is
 * information, not an error, and it must not interrupt a screen reader mid-sentence.
 * The accessible name is set explicitly because a status region does not take its
 * name from its contents.
 *
 * No retry button on purpose. The `online` event re-renders this automatically, and
 * a retry that cannot reach the network is a lie with a tap target on it.
 */
export function OfflineBanner({
  online,
  stale,
}: {
  online: boolean;
  stale: boolean;
}) {
  if (online && !stale) return null;

  const message = online
    ? "Couldn't refresh — showing your last synced progress."
    : "You're offline. Showing your last synced progress.";

  return (
    <div
      className={styles.banner}
      role="status"
      aria-label={online ? `Not up to date. ${message}` : `Offline. ${message}`}
    >
      <span className={styles.icon} aria-hidden="true">
        <SensorsIcon size={18} />
      </span>
      <span className={styles.text}>{message}</span>
    </div>
  );
}
