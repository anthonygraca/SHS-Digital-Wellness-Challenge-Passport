import type { Task } from "../../types/challenge";
import { WeekStatus } from "../../types/challenge";
import styles from "./WeekTile.module.css";

interface WeekTileProps {
  task: Task;
}

/**
 * WeekTile component (US-5): displays a single week/task with status indicator.
 *
 * Visual states:
 * - locked: grayed out, lock icon, future week not yet available
 * - available: highlighted, current/past week ready to complete
 * - complete: checkmark, completed week
 */
export function WeekTile({ task }: WeekTileProps) {
  const statusClass = {
    [WeekStatus.LOCKED]: styles.locked,
    [WeekStatus.AVAILABLE]: styles.available,
    [WeekStatus.COMPLETE]: styles.complete,
  }[task.status];

  const statusLabel = {
    [WeekStatus.LOCKED]: "Locked",
    [WeekStatus.AVAILABLE]: "Available",
    [WeekStatus.COMPLETE]: "Complete",
  }[task.status];

  const statusIcon = {
    [WeekStatus.LOCKED]: "🔒",
    [WeekStatus.AVAILABLE]: "📍",
    [WeekStatus.COMPLETE]: "✓",
  }[task.status];

  return (
    <article className={`${styles.tile} ${statusClass}`}>
      <div className={styles.statusBadge} aria-label={statusLabel}>
        <span className={styles.statusIcon}>{statusIcon}</span>
        <span className={styles.statusLabel}>{statusLabel}</span>
      </div>

      <div className={styles.content}>
        <h3 className={styles.weekNumber}>Week {task.week_no}</h3>
        <h4 className={styles.title}>{task.title}</h4>

        {task.caption && <p className={styles.caption}>{task.caption}</p>}

        <div className={styles.metadata}>
          {task.location && (
            <div className={styles.metaItem}>
              <span className={styles.metaIcon}>📍</span>
              <span className={styles.metaText}>{task.location}</span>
            </div>
          )}

          <div className={styles.metaItem}>
            <span className={styles.metaIcon}>📅</span>
            <span className={styles.metaText}>
              {formatDateRange(task.date_start, task.date_end)}
            </span>
          </div>

          {task.is_required && (
            <div className={styles.requiredBadge}>Required for prize</div>
          )}
        </div>
      </div>
    </article>
  );
}

function formatDateRange(startStr: string, endStr: string): string {
  const start = new Date(startStr);
  const end = new Date(endStr);

  const startFormatted = start.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  const endFormatted = end.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  return `${startFormatted} - ${endFormatted}`;
}
