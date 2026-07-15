import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../../../api/reports";
import type { ParticipationReport } from "../../../types/report";
import { SchoolIcon } from "../../icons";
import styles from "./Reports.module.css";

/** Share of enrolled students who finished a week, guarded for an empty cohort. */
function percent(completed: number, enrolled: number): number {
  return enrolled > 0 ? Math.round((completed / enrolled) * 100) : 0;
}

/**
 * Reporting dashboard (FR-F1 / US-21) — screen A1 of the design prototype:
 * enrollment total plus a per-week completion funnel showing where students
 * drop off. Aggregate counts only, never per-student rows (FR-F6).
 *
 * Always reports the campus's active challenge, which the server resolves — the
 * screen takes no challenge id, because "the challenge running now" is the only
 * one an admin can report on.
 */
export function Reports() {
  const navigate = useNavigate();
  const [report, setReport] = useState<ParticipationReport | null>(null);
  const [noActive, setNoActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await api.getParticipationReport();
      setReport(next);
      setNoActive(false);
      setError(null);
    } catch (e) {
      if (e instanceof api.ApiError && e.status === 404) {
        // Not a failure — the campus simply has nothing published yet.
        setNoActive(true);
        setReport(null);
        setError(null);
        return;
      }
      // A failed refresh keeps the numbers already on screen rather than
      // blanking them; only speak up when there is nothing to keep.
      setReport((prev) => {
        if (prev === null) {
          setError(
            e instanceof api.ApiError ? e.message : "Could not load the report",
          );
        }
        return prev;
      });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

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
        <button
          type="button"
          className={styles.refreshBtn}
          onClick={() => void refresh()}
        >
          Refresh
        </button>
      </header>

      <main className={styles.content}>
        {report && (
          <p className={styles.eyebrow}>
            {report.challenge.semester} · {report.challenge.name}
          </p>
        )}
        <h1 className={styles.title}>Reporting dashboard</h1>

        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}

        {noActive && (
          <p className={styles.empty}>
            No published challenge yet — publish one in the Challenge builder to
            see participation here.
          </p>
        )}

        {!report && !error && !noActive && <p className={styles.empty}>Loading…</p>}

        {report && (
          <>
            <section className={styles.statCard}>
              <span className={styles.statIcon}>
                <SchoolIcon size={22} />
              </span>
              <div className={styles.statValue} role="status">
                {report.total_enrollments}
              </div>
              <h2 className={styles.statLabel}>Enrolled</h2>
            </section>

            <section className={styles.funnelCard}>
              <h2 className={styles.cardLabel}>Per-week completion funnel</h2>
              {report.weeks.length === 0 ? (
                <p className={styles.funnelEmpty}>
                  This challenge has no weeks yet.
                </p>
              ) : (
                <ol
                  className={styles.funnel}
                  aria-label="Per-week completion funnel"
                >
                  {report.weeks.map((w) => {
                    const pct = percent(w.completed_count, report.total_enrollments);
                    return (
                      <li key={w.task_id} className={styles.funnelRow}>
                        <span className={styles.weekLabel}>Week {w.week_no}</span>
                        <span className={styles.track} aria-hidden="true">
                          <span
                            className={styles.fill}
                            style={{ width: `${pct}%` }}
                          />
                        </span>
                        <span className={styles.value}>
                          {w.completed_count} · {pct}%
                        </span>
                      </li>
                    );
                  })}
                </ol>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
