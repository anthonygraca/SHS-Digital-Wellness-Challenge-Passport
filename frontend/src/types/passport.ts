export type WeekStatus = "locked" | "available" | "complete";

export interface PassportWeek {
  weekNo: number;
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

export interface Passport {
  challengeName: string;
  theme: string;
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
