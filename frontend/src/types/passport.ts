export type WeekStatus = "locked" | "available" | "complete";

export interface PassportWeek {
  weekNo: number;
  taskId: number; // Added for US-15: task ID for check-in endpoint
  title: string;
  caption: string;
  activityType: string;
  location: string;
  // Null when the admin authored the task without a date window (US-11).
  dateStart: string | null;
  dateEnd: string | null;
  prize: string;
  required: boolean;
  status: WeekStatus;
}

/**
 * The challenge's theme resolved to data (US-13 / FR-B4): everything needed to
 * skin the app, so a re-skin ships no code (NFR-6).
 */
export interface ThemeConfig {
  id: string;
  /** CSS custom-property suffix -> value; applied as `--wp-<key>`. */
  palette: Record<string, string>;
  logoUrl: string | null;
  heroUrl: string | null;
  appTitle: string;
  tagline: string;
  copyTone: string;
}

export interface Passport {
  challengeName: string;
  /** The theme's id, which also selects its static token block in tokens.css. */
  theme: string;
  /** Null for the default theme (challenge has no theme, or it is unknown). */
  themeConfig: ThemeConfig | null;
  totalWeeks: number;
  completedWeeks: number;
  remainingWeeks: number;
  /** Required-task counts backing the prize-eligibility indicator (US-7). */
  requiredTotal: number;
  requiredCompleted: number;
  /** Derived: true once every required task is complete. */
  prizeEligible: boolean;
  weeks: PassportWeek[];
}

/** Result of a successful QR check-in (US-8): refreshed passport plus the tip to show. */
export interface CheckInResult {
  passport: Passport;
  /** Personalized post-check-in tip (FR-E1). */
  tip: string;
  /** The week that just flipped to complete. */
  weekNo: number;
  title: string;
}
