import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "../../auth/SessionProvider";
import { isAdminSession } from "../../auth/roles";
import { ApiError } from "../../api/challenges";
import { EligibilityBlocked } from "../EligibilityBlocked/EligibilityBlocked";
import { OfflineBanner } from "../OfflineBanner/OfflineBanner";
import { readPassportSnapshot, writePassportSnapshot } from "../../offline/snapshot";
import { useOnlineStatus } from "../../offline/useOnlineStatus";
import {
  fetchPassport,
  recordContentView,
  scanCheckIn,
} from "../../passport/passport";
import type {
  CheckInResult,
  Passport as PassportData,
  WeekStatus,
} from "../../types/passport";
import { useTheme } from "../../theme/ThemeProvider";
import { resolveThemeCopy } from "../../theme/themes";
import CrisisResources from "../CrisisResources/CrisisResources";
import { BoltIcon, CheckCircleIcon, LockIcon, TrophyIcon } from "../icons";
import { KnowledgeCheck } from "./KnowledgeCheck";
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

type OnScan = (token: string) => Promise<CheckInResult>;

/** Presentational passport: progress countdown, week tiles, and a detail sheet. */
export function PassportView({
  passport,
  onScan,
  online = true,
  stale = false,
}: {
  passport: PassportData;
  onScan?: OnScan;
  /** Drives the offline banner and the refusal to start a network action (US-6). */
  online?: boolean;
  /** Whether `passport` came from the offline cache rather than a live fetch. */
  stale?: boolean;
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
  const selectedWeek =
    selectedWeekNo != null
      ? (weeks.find((w) => w.weekNo === selectedWeekNo) ?? null)
      : null;

  // Event-QR scan flow (US-8): scanner overlay, then a success (tip) or error sheet.
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scanResult, setScanResult] = useState<CheckInResult | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  // Why an action was refused offline (US-6 / FR-C4), null when nothing was refused.
  const [offlineNotice, setOfflineNotice] = useState<string | null>(null);

  // Escape closes the detail sheet.
  useEffect(() => {
    if (selectedWeek == null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedWeekNo(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedWeek]);

  /**
   * Open a week's detail sheet, and record that the student read it (FR-F3 / US-23).
   *
   * In the click handler rather than an effect on `selectedWeekNo`, deliberately.
   * An effect would fire twice per open under StrictMode's double-invoke and
   * inflate every count in the engagement report; a click happens once because a
   * student clicked once. It would also re-fire on any re-render that re-ran the
   * effect, which is a re-render, not a read.
   *
   * Not awaited: the sheet is already open by the time the request lands, and
   * recordContentView swallows its own failures. Telemetry does not get to make a
   * student wait, or fail.
   */
  function openWeek(weekNo: number) {
    setSelectedWeekNo(weekNo);
    void recordContentView(weekNo, "week_detail");
  }

  function openScanner() {
    if (!online) {
      // The scanner never mounts, so the camera never starts and onScan is
      // unreachable. Nothing to queue: the server checks each token's freshness, so
      // a scan replayed later would be rejected anyway — after we had already told
      // the student they were checked in. Refusing now is the only honest answer.
      setOfflineNotice(
        "Scanning a QR code needs a connection. Nothing was recorded — reconnect and try again.",
      );
      return;
    }
    setScanResult(null);
    setScanError(null);
    setScannerOpen(true);
  }

  // Check-in is QR-only: from a week's detail sheet, close the sheet and hand off
  // to the same scanner. There is no manual "mark complete" — a real event QR is
  // the sole way to complete a task.
  function scanFromSheet() {
    setSelectedWeekNo(null);
    openScanner();
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
      <OfflineBanner online={online} stale={stale} />
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
              onClick={() => openWeek(week.weekNo)}
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

            {/* Renders nothing when the week has no questions, which is most weeks.
                Deliberately does not gate the check-in below: FR-E4 says nothing about
                coupling them, and doing so would change the UC-3 core loop. Offline it
                refuses to submit rather than queueing, same as check-in (US-6). */}
            <KnowledgeCheck weekNo={selectedWeek.weekNo} online={online} />

            {selectedWeek.status === "complete" ? (
              <button type="button" className={styles.checkedIn} disabled>
                <CheckCircleIcon size={18} /> Checked in
              </button>
            ) : onScan ? (
              <button
                type="button"
                className={styles.checkIn}
                onClick={scanFromSheet}
              >
                <BoltIcon size={18} /> Scan QR to check in
              </button>
            ) : (
              <p className={styles.sheetCaption}>
                Scan the event QR to check in.
              </p>
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

      {offlineNotice && (
        <div className={styles.backdrop} onClick={() => setOfflineNotice(null)}>
          <div
            className={styles.sheet}
            role="dialog"
            aria-modal="true"
            aria-label="Connection required"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.sheetHandle} aria-hidden="true" />
            <button
              type="button"
              className={styles.close}
              onClick={() => setOfflineNotice(null)}
              aria-label="Close"
            >
              ✕
            </button>

            <h2 className={styles.sheetTitle}>You're offline</h2>
            <p className={styles.sheetCaption} role="alert">
              {offlineNotice}
            </p>
          </div>
        </div>
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
  scanCheckInFn?: (token: string) => Promise<CheckInResult>;
}

/**
 * Passport home (US-5 / FR-C2, FR-C3). Guards against being viewed signed-out,
 * loads the student's weeks + progress, and records event-QR check-ins. fetchData
 * and scanCheckInFn are injectable for tests.
 *
 * Check-in is QR-only (US-8): a task is completed solely by scanning the event's
 * QR code — there is no manual "mark complete" path.
 *
 * US-2 (FR-A3): current-student eligibility gate. A non-current student is blocked
 * with a friendly message and never sees a passport — checked before the fetch so
 * an ineligible session makes no request. The API enforces this independently.
 */
export function Passport({
  fetchData = fetchPassport,
  scanCheckInFn = scanCheckIn,
}: PassportProps) {
  const { session, passport: seeded, loading, signOut } = useSession();
  const [passport, setPassport] = useState<PassportData | null>(seeded ?? null);
  const [dataLoading, setDataLoading] = useState(seeded == null);
  // Whether what we are showing came from the cache rather than this load's fetch.
  const [stale, setStale] = useState(false);
  const online = useOnlineStatus();
  const { applyTheme } = useTheme();

  useEffect(() => {
    if (!session || !session.isCurrentStudent) return;
    // Paint the bootstrap seed the instant it arrives — that is the round trip this
    // screen no longer waits on. The fetch below still runs to revalidate, because a
    // seed is only ever as fresh as the app-load bootstrap that carried it: a remount,
    // or an admin's manual override landing mid-session, can leave it stale. The
    // revalidation is a single non-blocking request after paint, not the old
    // render-nothing-then-fetch waterfall.
    if (seeded) {
      setPassport(seeded);
      setStale(false);
      setDataLoading(false);
    }
    let active = true;
    void (async () => {
      try {
        const data = await fetchData();
        if (!active) return;
        // Only a successful fetch writes, and nothing here ever clears: a null is
        // any !res.ok, including a transient 500, and throwing away a good snapshot
        // over a blip would cost the student their offline passport. The signed-out
        // case is already handled where it belongs, in SessionProvider.
        if (data) writePassportSnapshot(data);
        setPassport(data);
        setStale(false);
      } catch {
        // Offline: fetch rejects instead of resolving !res.ok, so fetchPassport's
        // null-on-failure guard never runs. Left uncaught this strands the screen
        // on "Loading your passport…" permanently. A rejected fetch — not
        // navigator.onLine — is what proves the data on screen is not live.
        if (!active) return;
        // A failed *revalidation* must not blank a passport already painted from the
        // seed — that data is as good as the cache it would fall back to. Keep what
        // is shown; only reach for the snapshot when starting from nothing. Either
        // way the fetch failed, so mark it stale: the offline banner is honest now.
        setPassport((prev) => prev ?? readPassportSnapshot());
        setStale(true);
      } finally {
        // active-guarded: finally still runs when the effect was torn down
        // mid-flight, and setting state after unmount is a no-op worth avoiding.
        if (active) setDataLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [session, seeded, fetchData]);

  // The challenge's theme rides along on every passport response, so re-skinning
  // on a theme change (US-13) costs nothing but this hand-off — and a scan refresh
  // re-applies it for free.
  useEffect(() => {
    if (passport) applyTheme(passport.theme, passport.themeConfig);
  }, [passport, applyTheme]);

  // Scan flow: record the check-in, refresh progress, and let the view surface the
  // tip. Errors (duplicate / invalid token) propagate for the view to display.
  async function handleScan(token: string): Promise<CheckInResult> {
    const result = await scanCheckInFn(token);
    setPassport(result.passport);
    return result;
  }

  if (loading) return <div className={styles.center}>Loading…</div>;
  if (!session) return <Navigate to="/" replace />;
  // The manifest's start_url is /passport, so this is where an installed app opens —
  // including for staff. Without this they would land on "not eligible to join",
  // which roles.ts already calls the wrong answer for an admin. Only admins leave,
  // so this cannot bounce against the landing's mirror-image redirect.
  if (isAdminSession(session)) return <Navigate to="/admin" replace />;
  if (!session.isCurrentStudent) return <EligibilityBlocked />;

  return (
    <>
      {dataLoading ? (
        <div className={styles.center}>Loading your passport…</div>
      ) : passport ? (
        <PassportView
          passport={passport}
          onScan={handleScan}
          online={online}
          stale={stale}
        />
      ) : !online ? (
        // Offline with nothing cached. The branch below would say "no active
        // challenge yet", which we have no way of knowing and is probably false —
        // we never reached the server to ask.
        <div className={styles.center} role="status">
          You're offline and haven't synced your passport yet. Reconnect to load
          your progress.
        </div>
      ) : (
        <div className={styles.center}>
          No active challenge yet — check back soon.
        </div>
      )}
      {/*
        Outside every conditional above, so the crisis affordance is on screen in each
        state this route can be in — loaded, loading, offline with nothing cached, and
        "no active challenge yet". A student in crisis at a campus that has published
        nothing is exactly the student the last branch strands, and FR-E3 does not depend
        on a challenge existing any more than the API route does.
      */}
      <div className={styles.signoutBar}>
        <CrisisResources />
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
