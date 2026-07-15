import { useCallback, useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import * as api from "../../../api/challenges";
import type { Challenge, CheckIn } from "../../../types/challenge";
import { CheckCircleIcon, SensorsIcon } from "../../icons";
import { CompletionOverridePanel } from "../ChallengeBuilder/ChallengeBuilder";
import styles from "./LiveOps.module.css";

/** How often the check-in count refreshes while the dashboard is open. */
const POLL_MS = 5000;
const RECENT_LIMIT = 6;

function relTime(ts: string, now: number) {
  const t = new Date(ts).getTime();
  if (Number.isNaN(t)) return ts;
  const s = Math.max(0, Math.floor((now - t) / 1000));
  if (s < 10) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return new Date(t).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

/**
 * Live event dashboard (FR-D4 / US-28): the event QR students scan plus a
 * check-in count that refreshes while the event runs. This screen is meant to
 * be projected or shown at the door, so the feed identifies students only by
 * check-in number — full identities live behind the Manual override panel.
 */
export function LiveOps() {
  const params = useParams();
  const navigate = useNavigate();
  const challengeId = Number(params.challengeId);
  const taskId = Number(params.taskId);

  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [checkins, setCheckins] = useState<CheckIn[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [overriding, setOverriding] = useState(false);
  // Timestamp of the last successful poll, so relative times stay coherent.
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!Number.isFinite(challengeId)) return;
    let cancelled = false;
    api
      .getChallenge(challengeId)
      .then((c) => { if (!cancelled) setChallenge(c); })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof api.ApiError ? e.message : "Could not load the event");
        }
      });
    return () => { cancelled = true; };
  }, [challengeId]);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listCheckIns(challengeId, taskId);
      setCheckins(list);
      setNow(Date.now());
    } catch (e) {
      // A failed poll keeps the last good count; the next tick retries. Only
      // surface the error while there is nothing on screen yet.
      setCheckins((prev) => {
        if (prev === null) {
          setError(e instanceof api.ApiError ? e.message : "Could not load check-ins");
        }
        return prev;
      });
    }
  }, [challengeId, taskId]);

  useEffect(() => {
    if (!Number.isFinite(challengeId) || !Number.isFinite(taskId)) return;
    void refresh();
    const id = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(id);
  }, [challengeId, taskId, refresh]);

  if (!Number.isFinite(challengeId) || !Number.isFinite(taskId)) {
    return <Navigate to="/admin" replace />;
  }

  const task = challenge?.tasks.find((t) => t.id === taskId) ?? null;
  const recent = checkins
    ? [...checkins]
        .sort((a, b) => b.ts.localeCompare(a.ts))
        .slice(0, RECENT_LIMIT)
    : [];

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <button
          type="button"
          className={styles.backBtn}
          onClick={() => navigate("/admin")}
        >
          ← Challenge builder
        </button>
      </header>

      <main className={styles.content}>
        <h1 className={styles.title}>Live event</h1>

        {error && <p className={styles.error} role="alert">{error}</p>}

        {!challenge && !error && <p className={styles.empty}>Loading…</p>}

        {challenge && !task && (
          <p className={styles.empty}>Task not found in this challenge.</p>
        )}

        {task && (
          <>
            <p className={styles.subtitle}>
              Week {task.position} · {task.title}
              {task.location ? ` · ${task.location}` : ""}
            </p>

            <div className={styles.grid}>
              <section className={styles.qrCard}>
                <h2 className={styles.cardLabel}>
                  Event QR — students scan to check in
                </h2>
                {task.qr_token ? (
                  <div
                    className={styles.qrBox}
                    aria-label={`Event check-in QR for ${task.title}`}
                  >
                    <QRCodeSVG value={task.qr_token} size={178} marginSize={2} />
                  </div>
                ) : (
                  <p className={styles.recentEmpty}>
                    No QR token on this task yet.
                  </p>
                )}
              </section>

              <div className={styles.column}>
                <section className={styles.countCard}>
                  <h2 className={styles.cardLabel}>Checked in — live</h2>
                  <div className={styles.count} role="status">
                    {checkins ? checkins.length : "—"}
                  </div>
                  <div className={styles.liveRow}>
                    <SensorsIcon size={15} />
                    updating in real time
                  </div>
                  <button
                    type="button"
                    className={styles.overrideBtn}
                    onClick={() => setOverriding(true)}
                  >
                    + Manual override
                  </button>
                </section>

                <section className={styles.recentCard}>
                  <h2 className={styles.cardLabel}>Recent check-ins</h2>
                  {recent.length === 0 ? (
                    <p className={styles.recentEmpty}>
                      No check-ins yet — waiting for the first scan.
                    </p>
                  ) : (
                    <ul className={styles.recentList} aria-label="Recent check-ins">
                      {recent.map((c) => (
                        <li key={c.id} className={styles.recentRow}>
                          <span className={styles.recentIcon}>
                            <CheckCircleIcon size={18} />
                          </span>
                          <span className={styles.recentWho}>
                            Student · #{c.id}
                          </span>
                          <span className={styles.recentTime}>
                            {relTime(c.ts, now)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>
            </div>
          </>
        )}
      </main>

      {overriding && task && (
        <CompletionOverridePanel
          challengeId={challengeId}
          task={task}
          onClose={() => {
            setOverriding(false);
            void refresh();
          }}
        />
      )}
    </div>
  );
}
