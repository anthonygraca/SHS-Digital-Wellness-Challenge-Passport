import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listChallenges } from "../../../api/challenges";
import * as api from "../../../api/reports";
import type { ChallengeSummary } from "../../../types/challenge";
import type {
  AttendanceReport,
  ContentRef,
  EngagementReport,
  ParticipationReport,
} from "../../../types/report";
import { DownloadIcon, SchoolIcon } from "../../icons";
import styles from "./Reports.module.css";

/** The card's row label for each content ref, in the order the API sends them.
 *  Kept short enough to hold one line in the label rail at a phone width — the
 *  attendance card's "Auto (event QR)" sets the length these have to match. */
const CONTENT_LABEL: Record<ContentRef, string> = {
  week_detail: "Week details",
  tip: "Tips after scan",
};

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
 * Engagement (FR-F3 / US-23) — how much students use the content and the guide.
 *
 * Views, not viewers: a student who opens the same week twice engaged twice, which
 * is the grain the API counts and the number this card exists to show.
 *
 * The guide row is a structural 0 until the conversational guide ships (US-16),
 * and says so rather than showing a bare zero. "0" next to "Guide sessions" reads
 * as "nobody used it"; the truth is that nobody *can* yet, and those are different
 * findings for an admin deciding what to do about it.
 */
function EngagementCard({ report }: { report: EngagementReport }) {
  return (
    <section className={styles.engagementCard}>
      <h2 className={styles.cardLabel}>Engagement</h2>

      {report.total_content_views === 0 ? (
        // Same reason the attendance card branches on zero: with no views, every
        // row below would be a 0 next to a 0%-wide bar, which reads as a broken
        // card rather than an empty one.
        <p className={styles.engagementEmpty}>No content viewed yet.</p>
      ) : (
        <>
          <ul className={styles.contentList} aria-label="Content views by type">
            {report.content_views.map((v) => (
              <li key={v.content_ref} className={styles.contentRow}>
                <span className={styles.contentLabel}>
                  {CONTENT_LABEL[v.content_ref]}
                </span>
                <span className={styles.contentBar} aria-hidden="true">
                  <span
                    className={styles.contentFill}
                    style={{
                      width: `${percent(v.count, report.total_content_views)}%`,
                    }}
                  />
                </span>
                <span className={styles.contentValue}>{v.count}</span>
              </li>
            ))}
          </ul>
          <p className={styles.contentTotal}>
            {report.total_content_views} content{" "}
            {report.total_content_views === 1 ? "view" : "views"} in total
          </p>
        </>
      )}

      {/* The count carries no role="status": the enrolled tile is this screen's
          one live region, and a second would make both ambiguous. */}
      <div className={styles.guideRow}>
        <h3 className={styles.guideLabel}>Guide chat sessions</h3>
        {report.guide_sessions === 0 ? (
          <p className={styles.guideEmpty}>
            No guide sessions yet — the wellness guide isn’t available to students
            yet.
          </p>
        ) : (
          <p className={styles.guideValue}>{report.guide_sessions}</p>
        )}
      </div>
    </section>
  );
}

/** Hand the CSV to the browser as a download named the way the server named it. */
function saveFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  // The object URL pins the blob in memory until it is revoked, and nothing else
  // holds a reference to this one once the click is dispatched.
  URL.revokeObjectURL(url);
}

/**
 * Reporting dashboard (FR-F1 / US-21) — screen A1 of the design prototype:
 * enrollment total plus a per-week completion funnel showing where students
 * drop off. Aggregate counts only, never per-student rows (FR-F6).
 *
 * Reports on one challenge at a time, chosen with the selector (US-23's "both can
 * be viewed per challenge"). Selecting nothing means the campus's active
 * challenge, which the server resolves — that is what an admin opening the screen
 * means, and it is what the screen shows before the challenge list has loaded.
 *
 * One selector for every card, not one per card: the same reason the server shares
 * its challenge resolver across the routes. Three cards that could each be showing
 * a different semester would be three answers to a question nobody asked.
 *
 * The prize-list export (FR-F5 / US-26) is the one per-student read on the
 * screen, and it never renders those rows: the CSV goes straight to the
 * browser's downloads, so the dashboard itself stays aggregate. It follows the
 * selector too — a drawing has real prizes attached.
 */
export function Reports() {
  const navigate = useNavigate();
  const [report, setReport] = useState<ParticipationReport | null>(null);
  const [attendance, setAttendance] = useState<AttendanceReport | null>(null);
  const [engagement, setEngagement] = useState<EngagementReport | null>(null);
  const [challenges, setChallenges] = useState<ChallengeSummary[]>([]);
  // undefined, not null: it is passed straight to the API layer, which omits the
  // parameter entirely for undefined and so asks for the active challenge.
  const [selectedId, setSelectedId] = useState<number | undefined>(undefined);
  const [noActive, setNoActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const refresh = useCallback(async (challengeId?: number) => {
    try {
      // Promise.all rather than three awaits or allSettled: the cards describe
      // one moment in one challenge, so they land together or not at all. A
      // partial update could show a funnel from now beside an auto share from a
      // minute ago, and nothing on screen would say which was stale.
      const [participation, attendanceNext, engagementNext] = await Promise.all([
        api.getParticipationReport(challengeId),
        api.getAttendanceReport(challengeId),
        api.getEngagementReport(challengeId),
      ]);
      setReport(participation);
      setAttendance(attendanceNext);
      setEngagement(engagementNext);
      setNoActive(false);
      setError(null);
    } catch (e) {
      if (e instanceof api.ApiError && e.status === 404) {
        // Not a failure — the campus simply has nothing published yet. Every
        // route resolves the same challenge, so they 404 together.
        setNoActive(true);
        setReport(null);
        setAttendance(null);
        setEngagement(null);
        setError(null);
        return;
      }
      // A failed refresh keeps the numbers already on screen rather than
      // blanking them; only speak up when there is nothing to keep. Promise.all
      // set no card, so all three keep their last good read.
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
    void refresh(selectedId);
  }, [refresh, selectedId]);

  // The challenge list is fetched once and separately from the reports: it is the
  // control's own data, not part of the moment the cards describe, and a failure
  // to load it should cost the admin the selector rather than the dashboard.
  // Drafts are filtered out because they are not reportable — the server 404s on
  // one, so offering it would build a control that breaks the screen.
  useEffect(() => {
    void (async () => {
      try {
        const all = await listChallenges();
        setChallenges(all.filter((c) => c.status === "published"));
      } catch {
        setChallenges([]);
      }
    })();
  }, []);

  const exportPrizeList = useCallback(async () => {
    setExporting(true);
    try {
      const { blob, filename } = await api.exportPrizeCsv(selectedId);
      saveFile(blob, filename);
      setError(null);
    } catch (e) {
      // Unlike a failed refresh, this always speaks up: there is no stale file
      // on screen to fall back on, and an admin who gets no download owes an
      // explanation rather than silence.
      setError(
        e instanceof api.ApiError ? e.message : "Could not export the prize list",
      );
    } finally {
      setExporting(false);
    }
  }, [selectedId]);

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
          onClick={() => void refresh(selectedId)}
        >
          Refresh
        </button>
      </header>

      <main className={styles.content}>
        <div className={styles.header}>
          <div>
            {report && (
              <p className={styles.eyebrow}>
                {report.challenge.semester} · {report.challenge.name}
              </p>
            )}
            <h1 className={styles.title}>Reporting dashboard</h1>
          </div>

          {/* Only once a challenge has loaded: with nothing published there is
              no drawing to export, and the button would only 404. */}
          {report && (
            <button
              type="button"
              className={styles.exportBtn}
              onClick={() => void exportPrizeList()}
              disabled={exporting}
            >
              <DownloadIcon size={19} />
              {exporting ? "Exporting…" : "Export prize list (CSV)"}
            </button>
          )}
        </div>

        {/* More than one published challenge is what makes this a choice. With one,
            the eyebrow above already names it and a single-option select would be a
            control that cannot do anything. */}
        {challenges.length > 1 && (
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel} htmlFor="challenge-select">
              Challenge
            </label>
            <select
              id="challenge-select"
              className={styles.select}
              value={selectedId ?? ""}
              onChange={(e) =>
                setSelectedId(e.target.value === "" ? undefined : Number(e.target.value))
              }
            >
              {/* Empty value = no challenge_id = whatever is running now, which
                  keeps following the semester as it rolls over. */}
              <option value="">Active challenge</option>
              {challenges.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.semester} · {c.name}
                </option>
              ))}
            </select>
          </div>
        )}

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

        {report && attendance && engagement && (
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
            <EngagementCard report={engagement} />
          </>
        )}
      </main>
    </div>
  );
}
