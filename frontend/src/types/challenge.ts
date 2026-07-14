/**
 * Frontend types matching backend schemas for challenge and passport data (US-5).
 */

export enum WeekStatus {
  LOCKED = "locked",
  AVAILABLE = "available",
  COMPLETE = "complete",
}

export interface Task {
  id: number;
  challenge_id: number;
  week_no: number;
  title: string;
  caption: string | null;
  activity_type: string;
  location: string | null;
  date_start: string; // ISO date
  date_end: string; // ISO date
  is_required: boolean;
  order: number;
  status: WeekStatus;
}

export interface Challenge {
  id: number;
  campus_id: string;
  name: string;
  theme_name: string | null;
  semester: string;
  starts_on: string; // ISO date
  ends_on: string; // ISO date
  status: string;
  created_at: string; // ISO datetime
}

export interface Progress {
  total_weeks: number;
  completed: number;
  remaining: number;
  is_prize_eligible: boolean;
}

export interface Passport {
  challenge: Challenge;
  tasks: Task[];
  progress: Progress;
  enrolled_at: string; // ISO datetime
}
