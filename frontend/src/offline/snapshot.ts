import type { Passport } from "../types/passport";
import type { Session } from "../types/session";

/**
 * The last-synced session and passport, kept so the app can show real progress
 * with no connection (US-6 / FR-C4).
 *
 * The invariant that makes this safe: **a snapshot only ever survives because we
 * were offline.** Any authoritative "you are signed out" from the server clears
 * both keys, so the fallback can never resurrect a session the server has ended.
 * SessionProvider owns that lifecycle; see the note on clearOfflineSnapshot.
 *
 * Privacy: this is an SSO subject plus wellness-challenge participation on what is
 * often a shared phone. Not PHI, but close enough to want it gone the moment the
 * student signs out rather than lingering until the browser evicts it.
 */

// Versioned: a change to the Passport or Session shape must not feed a stale
// payload to a newer app. Bump the suffix and old snapshots are simply ignored.
const SESSION_KEY = "wp.offline.session.v1";
const PASSPORT_KEY = "wp.offline.passport.v1";

/**
 * Every localStorage access is wrapped. It throws outright in Safari private mode
 * and on quota exhaustion, and neither a failed read nor a failed write is worth
 * taking down a render over — the app just behaves as though nothing was cached.
 */
function readJson<T>(key: string, isValid: (value: unknown) => boolean): T | null {
  try {
    const raw = localStorage.getItem(key);
    if (raw == null) return null;
    const parsed: unknown = JSON.parse(raw);
    return isValid(parsed) ? (parsed as T) : null;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage full or blocked: offline viewing degrades, the app keeps working.
  }
}

// Structural guards, not full validation. They exist so a truncated write or a
// hand-edited key surfaces as "no snapshot" rather than white-screening PassportView
// on a missing field.
const looksLikeSession = (v: unknown): boolean =>
  typeof v === "object" && v !== null && typeof (v as Session).subject === "string";

const looksLikePassport = (v: unknown): boolean =>
  typeof v === "object" && v !== null && Array.isArray((v as Passport).weeks);

export function readSessionSnapshot(): Session | null {
  return readJson<Session>(SESSION_KEY, looksLikeSession);
}

export function writeSessionSnapshot(session: Session): void {
  writeJson(SESSION_KEY, session);
}

export function readPassportSnapshot(): Passport | null {
  return readJson<Passport>(PASSPORT_KEY, looksLikePassport);
}

export function writePassportSnapshot(passport: Passport): void {
  writeJson(PASSPORT_KEY, passport);
}

/**
 * Drop both keys. Deliberately all-or-nothing: a passport without its session is
 * unreachable, and a session without its passport would show a signed-in shell with
 * no data. They are cached as a pair, so they die as a pair.
 */
export function clearOfflineSnapshot(): void {
  try {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(PASSPORT_KEY);
  } catch {
    // Nothing to do — see readJson.
  }
}
