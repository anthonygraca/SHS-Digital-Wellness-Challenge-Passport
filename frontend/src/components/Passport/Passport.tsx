import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "../../auth/SessionProvider";
import { EligibilityBlocked } from "../EligibilityBlocked/EligibilityBlocked";
import { checkIn, fetchPassport } from "../../passport/passport";
import type { Passport as PassportData, WeekStatus } from "../../types/passport";
import { BoltIcon, CheckCircleIcon, LockIcon } from "../icons";
import styles from "./Passport.module.css";

const STATUS_LABEL: Record<WeekStatus, string> = {
  complete: "Complete",
  available: "Available",
  locked: "Locked",
};

function StatusIcon({ status }: { status: WeekStatus }) {
  if (status === "complete") return <CheckCircleIcon size={18} />;
  if (status === "available") return <BoltIcon size={18} />;
  return <LockIcon size={18} />;
}

/**
 * "Sep 2 – Sep 6" from two ISO dates (UTC so the day never shifts by tz). Either
 * end may be absent — the admin builder (US-11) allows a task with no date window,
 * or only one end of one — so fall back to whatever is known.
 */
function formatWindow(
  startIso: string | null,
  endIso: string | null,
): string {
  const fmt = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
  const start = startIso ? fmt.format(new Date(startIso)) : null;
  const end = endIso ? fmt.format(new Date(endIso)) : null;
  if (start && end) return `${start} – ${end}`;
  return start ?? end ?? "Dates TBA";
}

type OnCheckIn = (weekNo: number) => Promise<void> | void;

/** Presentational passport: progress countdown, week tiles, and a detail sheet. */
export function PassportView({
  passport,
  onCheckIn,
}: {
  passport: PassportData;
  onCheckIn?: OnCheckIn;
}) {
  const { challengeName, completedWeeks, totalWeeks, remainingWeeks, weeks } =
    passport;
  const pct = totalWeeks > 0 ? (completedWeeks / totalWeeks) * 100 : 0;

  const [selectedWeekNo, setSelectedWeekNo] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const selectedWeek =
    selectedWeekNo != null
      ? (weeks.find((w) => w.weekNo === selectedWeekNo) ?? null)
      : null;

  // Escape closes the detail sheet.
  useEffect(() => {
    if (selectedWeek == null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedWeekNo(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedWeek]);

  async function handleCheckIn() {
    if (!onCheckIn || selectedWeek == null) return;
    setSubmitting(true);
    try {
      await onCheckIn(selectedWeek.weekNo);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className={styles.screen}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>{challengeName}</p>
        <h1 className={styles.countdown}>
          {completedWeeks} of {totalWeeks} complete, {remainingWeeks} remaining
        </h1>
        <div
          className={styles.progressTrack}
          role="progressbar"
          aria-valuenow={completedWeeks}
          aria-valuemin={0}
          aria-valuemax={totalWeeks}
          aria-label="Weeks complete"
        >
          <div className={styles.progressFill} style={{ width: `${pct}%` }} />
        </div>
      </header>

      <ul className={styles.grid}>
        {weeks.map((week) => (
          <li key={week.weekNo} className={styles.gridItem}>
            <button
              type="button"
              className={`${styles.tile} ${styles[week.status]}`}
              onClick={() => setSelectedWeekNo(week.weekNo)}
              aria-label={`Week ${week.weekNo}: ${week.title}, ${STATUS_LABEL[week.status]}`}
            >
              <div className={styles.tileTop}>
                <span className={styles.weekNo}>Week {week.weekNo}</span>
                <span className={styles.status}>
                  <StatusIcon status={week.status} />
                  {STATUS_LABEL[week.status]}
                </span>
              </div>
              <span className={styles.title}>{week.title}</span>
              <span className={styles.activity}>{week.activityType}</span>
              <span className={styles.caption}>{week.caption}</span>
            </button>
          </li>
        ))}
      </ul>

      {selectedWeek && (
        <div
          className={styles.backdrop}
          onClick={() => setSelectedWeekNo(null)}
        >
          <div
            className={styles.sheet}
            role="dialog"
            aria-modal="true"
            aria-label={`Week ${selectedWeek.weekNo}: ${selectedWeek.title}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.sheetHandle} aria-hidden="true" />
            <button
              type="button"
              className={styles.close}
              onClick={() => setSelectedWeekNo(null)}
              aria-label="Close"
            >
              ✕
            </button>

            <p className={styles.eyebrow}>Week {selectedWeek.weekNo}</p>
            <h2 className={styles.sheetTitle}>{selectedWeek.title}</h2>
            <p className={styles.activity}>{selectedWeek.activityType}</p>
            <p className={styles.sheetCaption}>{selectedWeek.caption}</p>

            <dl className={styles.meta}>
              <div>
                <dt>Where</dt>
                <dd>{selectedWeek.location}</dd>
              </div>
              <div>
                <dt>When</dt>
                <dd>
                  {formatWindow(selectedWeek.dateStart, selectedWeek.dateEnd)}
                </dd>
              </div>
              <div>
                <dt>Prize</dt>
                <dd>{selectedWeek.prize}</dd>
              </div>
            </dl>

            {selectedWeek.status === "complete" ? (
              <button type="button" className={styles.checkedIn} disabled>
                <CheckCircleIcon size={18} /> Checked in
              </button>
            ) : (
              <button
                type="button"
                className={styles.checkIn}
                onClick={() => void handleCheckIn()}
                disabled={submitting || !onCheckIn}
              >
                {submitting ? "Checking in…" : "Check in"}
              </button>
            )}
          </div>
        </div>
      )}
    </main>
  );
}

interface PassportProps {
  fetchData?: () => Promise<PassportData | null>;
  checkInFn?: (weekNo: number) => Promise<PassportData | null>;
}

/**
 * Passport home (US-5 / FR-C2, FR-C3). Guards against being viewed signed-out,
 * loads the student's weeks + progress, and records manual check-ins. fetchData
 * and checkInFn are injectable for tests.
 *
 * US-2 (FR-A3): current-student eligibility gate. A non-current student is blocked
 * with a friendly message and never sees a passport — checked before the fetch so
 * an ineligible session makes no request. The API enforces this independently.
 */
export function Passport({
  fetchData = fetchPassport,
  checkInFn = checkIn,
}: PassportProps) {
  const { session, loading, signOut } = useSession();
  const [passport, setPassport] = useState<PassportData | null>(null);
  const [dataLoading, setDataLoading] = useState(true);

  useEffect(() => {
    if (!session || !session.isCurrentStudent) return;
    let active = true;
    void fetchData().then((data) => {
      if (!active) return;
      setPassport(data);
      setDataLoading(false);
    });
    return () => {
      active = false;
    };
  }, [session, fetchData]);

  async function handleCheckIn(weekNo: number) {
    const updated = await checkInFn(weekNo);
    if (updated) setPassport(updated);
  }

  if (loading) return <div className={styles.center}>Loading…</div>;
  if (!session) return <Navigate to="/" replace />;
  if (!session.isCurrentStudent) return <EligibilityBlocked />;

  return (
    <>
      {dataLoading ? (
        <div className={styles.center}>Loading your passport…</div>
      ) : passport ? (
        <PassportView passport={passport} onCheckIn={handleCheckIn} />
      ) : (
        <div className={styles.center}>
          No active challenge yet — check back soon.
        </div>
      )}
      <div className={styles.signoutBar}>
        <button
          type="button"
          className={styles.signout}
          onClick={() => void signOut()}
        >
          Sign out
        </button>
      </div>
    </>
  );
}
