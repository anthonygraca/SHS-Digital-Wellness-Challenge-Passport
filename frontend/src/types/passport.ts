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
  weeks: PassportWeek[];
}
