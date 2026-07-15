/**
 * TipNotification: Simple tip display after check-in (US-15).
 * Shows a brief personalized health tip as a slide-in notification.
 */
import { useEffect } from "react";
import type { CheckInResponse } from "../../types/checkin";
import { BoltIcon } from "../icons";
import styles from "./TipNotification.module.css";

interface TipNotificationProps {
  checkInData: CheckInResponse;
  onClose: () => void;
}

export function TipNotification({ checkInData, onClose }: TipNotificationProps) {
  const { task_title, personalized_tip, progress } = checkInData;
  const { tip, resource } = personalized_tip;
  const { remaining_required_tasks, is_prize_eligible } = progress;

  // Auto-dismiss after 8 seconds
  useEffect(() => {
    const timer = setTimeout(onClose, 8000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className={styles.container}>
      <div className={styles.notification}>
        <button
          type="button"
          className={styles.closeBtn}
          onClick={onClose}
          aria-label="Close"
        >
          ✕
        </button>

        <div className={styles.header}>
          <BoltIcon size={20} />
          <span className={styles.title}>Health Tip</span>
        </div>

        <p className={styles.taskTitle}>✓ {task_title}</p>

        <p className={styles.tip}>{tip}</p>

        {resource && (
          <p className={styles.resource}>
            <strong>Resource:</strong> {resource}
          </p>
        )}

        {is_prize_eligible ? (
          <div className={styles.badge}>🎉 Prize eligible!</div>
        ) : remaining_required_tasks === 1 ? (
          <div className={styles.badge}>1 more task to go!</div>
        ) : remaining_required_tasks <= 3 ? (
          <div className={styles.badge}>{remaining_required_tasks} tasks to go</div>
        ) : null}
      </div>
    </div>
  );
}
