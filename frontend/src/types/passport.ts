export type WeekStatus = "locked" | "available" | "complete";

export interface PassportWeek {
  weekNo: number;
  title: string;
  caption: string;
  activityType: string;
  location: string;
  dateStart: string;
  dateEnd: string;
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
