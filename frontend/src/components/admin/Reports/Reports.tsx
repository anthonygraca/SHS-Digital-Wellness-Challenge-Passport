import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../../../api/reports";
import type { AttendanceReport, ParticipationReport } from "../../../types/report";
import { SchoolIcon } from "../../icons";
import styles from "./Reports.module.css";

/** Share of `whole` that `part` makes up, guarded for an empty denominator. */
function percent(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 100) : 0;
}

/**
 * Attendance capture (FR-F2 / US-22) — the design prototype's second A1 card.
 * "Automatic" means event_qr and nothing else: a staff or manual check-in is a
 * person doing the capture, which is exactly the effort this card measures.
 *
 * The API also ships a `staff` bucket, always 0 today because no write path
 * mints it. It folds into "Manual / staff" rather than getting a row of its own —
 * a permanently-empty third row would cost more attention than it pays back.
 */
function AttendanceCard({ report }: { report: AttendanceReport }) {
  // A lookup, not a search that can legitimately miss: the API ships all three
  // buckets every time. The ?? satisfies the type, it is not a real branch.
  const autoCount = report.methods.find((m) => m.method === "event_qr")?.count ?? 0;
  const autoPct = percent(autoCount, report.total_checkins);
  // Derived by subtraction, not percent(total - auto, total): the two rows are
  // one whole, and two independent roundings can sum to 101 (67 of 200 rounds to
  // 34%, and the remaining 66.5% rounds to 67%) — which the stacked bar would
  // render as an overflowing segment.
  const manualPct = 100 - autoPct;

  return (
    <section className={styles.attendanceCard}>
      <h2 className={styles.cardLabel}>Attendance capture</h2>
      {report.total_checkins === 0 ? (
        // Not a NaN guard — percent() already returns 0. Without this branch the
        // complement above would paint a bar that is 100% manual for a challenge
        // with no check-ins at all, which is a lie rather than a blank.
        <p className={styles.attendanceEmpty}>No check-ins recorded yet.</p>
      ) : (
        <>
          <ul className={styles.methodList} aria-label="Attendance capture by method">
            <li className={styles.methodRow}>
              <span
                className={`${styles.swatch} ${styles.swatchAuto}`}
                aria-hidden="true"
              />
              <span className={styles.methodLabel}>Auto (event QR)</span>
              <span className={styles.methodPct}>{autoPct}%</span>
            </li>
            <li className={styles.methodRow}>
              <span
                className={`${styles.swatch} ${styles.swatchManual}`}
                aria-hidden="true"
              />
              <span className={styles.methodLabel}>Manual / staff</span>
              <span className={styles.methodPct}>{manualPct}%</span>
            </li>
          </ul>
          {/* aria-hidden: the bar restates the two rows above, exactly as the
              funnel's .track restates its count. */}
          <div className={styles.stack} aria-hidden="true">
            <span className={styles.stackAuto} style={{ width: `${autoPct}%` }} />
            <span className={styles.stackManual} />
          </div>
          <p className={styles.methodTotal}>
            {autoCount} of {report.total_checkins} check-ins captured automatically
          </p>
        </>
      )}
    </section>
  );
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
  const [attendance, setAttendance] = useState<AttendanceReport | null>(null);
  const [noActive, setNoActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      // Promise.all rather than two awaits or allSettled: the two cards describe
      // one moment in one challenge, so they land together or not at all. A
      // partial update could show a funnel from now beside an auto share from a
      // minute ago, and nothing on screen would say which was stale.
      const [participation, attendanceNext] = await Promise.all([
        api.getParticipationReport(),
        api.getAttendanceReport(),
      ]);
      setReport(participation);
      setAttendance(attendanceNext);
      setNoActive(false);
      setError(null);
    } catch (e) {
      if (e instanceof api.ApiError && e.status === 404) {
        // Not a failure — the campus simply has nothing published yet. Both
        // routes resolve the same active challenge, so they 404 together.
        setNoActive(true);
        setReport(null);
        setAttendance(null);
        setError(null);
        return;
      }
      // A failed refresh keeps the numbers already on screen rather than
      // blanking them; only speak up when there is nothing to keep. Promise.all
      // set neither card, so both keep their last good read.
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

        {report && attendance && (
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

            <AttendanceCard report={attendance} />
          </>
        )}
      </main>
    </div>
  );
}
