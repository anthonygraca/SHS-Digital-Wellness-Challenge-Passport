export interface Task {
  id: number;
  challenge_id: number;
  position: number;
  title: string;
  caption: string;
  activity_type: string;
  location: string;
  date_window_start: string | null; // ISO date "YYYY-MM-DD"
  date_window_end: string | null;
  prize: string;
  required: boolean;
  created_at: string;
  updated_at: string;
}

export interface Challenge {
  id: number;
  campus_id: string;
  name: string;
  semester: string;
  start_date: string; // ISO date "YYYY-MM-DD"
  end_date: string;
  status: "draft" | "published";
  tasks: Task[];
  created_at: string;
  updated_at: string;
}

/** Lightweight list-view — no tasks array. */
export interface ChallengeSummary {
  id: number;
  campus_id: string;
  name: string;
  semester: string;
  start_date: string;
  end_date: string;
  status: "draft" | "published";
  created_at: string;
  updated_at: string;
}

export interface ChallengeCreate {
  name: string;
  semester: string;
  start_date: string;
  end_date: string;
}

export interface ChallengeUpdate {
  name?: string;
  semester?: string;
  start_date?: string;
  end_date?: string;
}

export interface TaskCreate {
  title: string;
  caption?: string;
  activity_type?: string;
  location?: string;
  date_window_start?: string | null;
  date_window_end?: string | null;
  prize?: string;
  required?: boolean;
}

export interface TaskUpdate {
  title?: string;
  caption?: string;
  activity_type?: string;
  location?: string;
  date_window_start?: string | null;
  date_window_end?: string | null;
  prize?: string;
  required?: boolean;
}

export interface TaskReorder {
  task_ids: number[];
}
