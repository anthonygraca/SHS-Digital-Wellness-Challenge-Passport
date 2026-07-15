import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "../../auth/SessionProvider";
import { ApiError } from "../../api/challenges";
import { EligibilityBlocked } from "../EligibilityBlocked/EligibilityBlocked";
import { checkIn, fetchPassport, scanCheckIn } from "../../passport/passport";
import type {
  CheckInResult,
  Passport as PassportData,
  WeekStatus,
} from "../../types/passport";
import { useTheme } from "../../theme/ThemeProvider";
import { resolveThemeCopy } from "../../theme/themes";
import { BoltIcon, CheckCircleIcon, LockIcon, TrophyIcon } from "../icons";
import { QrScanner } from "./QrScanner";
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

/**
 * Prize-eligibility indicator (US-7 / FR-C5). Eligibility is derived server-side
 * from required-task completion; this just renders the status and the progress
 * toward it so a student knows if they have met the drawing requirements.
 */
function PrizeIndicator({
  eligible,
  requiredCompleted,
  requiredTotal,
}: {
  eligible: boolean;
  requiredCompleted: number;
  requiredTotal: number;
}) {
  const noun = `required task${requiredTotal === 1 ? "" : "s"}`;
  const status = eligible ? "Prize eligible" : "Not yet eligible";
  const detail = eligible
    ? `All ${requiredTotal} ${noun} complete — you're in the drawing`
    : `${requiredCompleted} of ${requiredTotal} ${noun} complete`;
  return (
    <div
      className={styles.prize}
      data-eligible={eligible}
      role="status"
      aria-label={`Prize eligibility: ${status}. ${detail}.`}
    >
      <span className={styles.prizeIcon} aria-hidden="true">
        {eligible ? <TrophyIcon size={20} /> : <LockIcon size={18} />}
      </span>
      <span className={styles.prizeText}>
        <span className={styles.prizeStatus}>{status}</span>
        <span className={styles.prizeDetail}>{detail}</span>
      </span>
    </div>
  );
}

type OnCheckIn = (weekNo: number) => Promise<void> | void;
type OnScan = (token: string) => Promise<CheckInResult>;

/** Presentational passport: progress countdown, week tiles, and a detail sheet. */
export function PassportView({
  passport,
  onCheckIn,
  onScan,
}: {
  passport: PassportData;
  onCheckIn?: OnCheckIn;
  onScan?: OnScan;
}) {
  const {
    challengeName,
    theme: themeId,
    themeConfig: theme,
    completedWeeks,
    totalWeeks,
    remainingWeeks,
    requiredCompleted,
    requiredTotal,
    prizeEligible,
    weeks,
  } = passport;
  const pct = totalWeeks > 0 ? (completedWeeks / totalWeeks) * 100 : 0;

  // Themed branding and copy (US-13), read straight off the passport. The palette
  // is applied separately by ThemeProvider as CSS custom properties, so every
  // style below keeps working through a re-skin untouched.
  const { appTitle, tagline } = resolveThemeCopy(themeId, theme);
  // Hero art sits behind a scrim of the theme's own surface color, so the header
  // text keeps the contrast it was designed for whatever image an admin picks
  // (and whether the theme is light or dark). No art = the plain surface.
  const heroStyle = theme?.heroUrl
    ? {
        backgroundImage:
          `linear-gradient(160deg, color-mix(in srgb, var(--wp-surface) 80%, transparent), ` +
          `color-mix(in srgb, var(--wp-surface) 94%, transparent)), url(${theme.heroUrl})`,
        backgroundSize: "cover",
        backgroundPosition: "center",
      }
    : undefined;

  const [selectedWeekNo, setSelectedWeekNo] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const selectedWeek =
    selectedWeekNo != null
      ? (weeks.find((w) => w.weekNo === selectedWeekNo) ?? null)
      : null;

  // Event-QR scan flow (US-8): scanner overlay, then a success (tip) or error sheet.
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scanResult, setScanResult] = useState<CheckInResult | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

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

  function openScanner() {
    setScanResult(null);
    setScanError(null);
    setScannerOpen(true);
  }

  async function handleDecode(token: string) {
    if (!onScan) return;
    setScannerOpen(false);
    try {
      const result = await onScan(token);
      setScanResult(result);
      setScanError(null);
    } catch (e) {
      setScanError(
        e instanceof ApiError ? e.message : "Check-in failed. Please try again.",
      );
      setScanResult(null);
    }
  }

  return (
    <main className={styles.screen}>
      <header className={styles.header} style={heroStyle}>
        <div className={styles.brand}>
          {theme?.logoUrl && (
            <img className={styles.logo} src={theme.logoUrl} alt="" />
          )}
          <span className={styles.appTitle}>{appTitle}</span>
        </div>
        <p className={styles.eyebrow}>{challengeName}</p>
        <h1 className={styles.countdown}>
          {completedWeeks} of {totalWeeks} complete, {remainingWeeks} remaining
        </h1>
        {tagline && <p className={styles.tagline}>{tagline}</p>}
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
        <PrizeIndicator
          eligible={prizeEligible}
          requiredCompleted={requiredCompleted}
          requiredTotal={requiredTotal}
        />
        {onScan && (
          <button
            type="button"
            className={styles.scanCta}
            onClick={openScanner}
          >
            <BoltIcon size={18} /> Scan QR to check in
          </button>
        )}
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

      {scannerOpen && onScan && (
        <QrScanner
          onDecode={(token) => void handleDecode(token)}
          onClose={() => setScannerOpen(false)}
        />
      )}

      {(scanResult || scanError) && (
        <div className={styles.backdrop} onClick={() => { setScanResult(null); setScanError(null); }}>
          <div
            className={styles.sheet}
            role="dialog"
            aria-modal="true"
            aria-label={scanResult ? "Check-in complete" : "Check-in failed"}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.sheetHandle} aria-hidden="true" />
            <button
              type="button"
              className={styles.close}
              onClick={() => { setScanResult(null); setScanError(null); }}
              aria-label="Close"
            >
              ✕
            </button>

            {scanResult ? (
              <>
                <p className={styles.eyebrow}>Week {scanResult.weekNo}</p>
                <h2 className={styles.sheetTitle}>
                  <CheckCircleIcon size={22} /> {scanResult.title} complete!
                </h2>
                <p className={styles.tip} role="status">
                  {scanResult.tip}
                </p>
              </>
            ) : (
              <>
                <h2 className={styles.sheetTitle}>Couldn't check in</h2>
                <p className={styles.sheetCaption} role="alert">
                  {scanError}
                </p>
              </>
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
  scanCheckInFn?: (token: string) => Promise<CheckInResult>;
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
  scanCheckInFn = scanCheckIn,
}: PassportProps) {
  const { session, loading, signOut } = useSession();
  const [passport, setPassport] = useState<PassportData | null>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const { applyTheme } = useTheme();

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

  // The challenge's theme rides along on every passport response, so re-skinning
  // on a theme change (US-13) costs nothing but this hand-off — and a check-in or
  // scan refresh re-applies it for free.
  useEffect(() => {
    if (passport) applyTheme(passport.theme, passport.themeConfig);
  }, [passport, applyTheme]);

  async function handleCheckIn(weekNo: number) {
    const updated = await checkInFn(weekNo);
    if (updated) setPassport(updated);
  }

  // Scan flow: record the check-in, refresh progress, and let the view surface the
  // tip. Errors (duplicate / invalid token) propagate for the view to display.
  async function handleScan(token: string): Promise<CheckInResult> {
    const result = await scanCheckInFn(token);
    setPassport(result.passport);
    return result;
  }

  if (loading) return <div className={styles.center}>Loading…</div>;
  if (!session) return <Navigate to="/" replace />;
  if (!session.isCurrentStudent) return <EligibilityBlocked />;

  return (
    <>
      {dataLoading ? (
        <div className={styles.center}>Loading your passport…</div>
      ) : passport ? (
        <PassportView
          passport={passport}
          onCheckIn={handleCheckIn}
          onScan={handleScan}
        />
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
