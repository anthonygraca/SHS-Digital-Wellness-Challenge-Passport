/** The joinable challenge, trimmed to what the enroll UI needs. */
export interface ActiveChallenge {
  id: number;
  name: string;
}

/** Drives the landing screen: is there something to join, and am I in it? */
export interface EnrollmentStatus {
  active_challenge: ActiveChallenge | null;
  enrolled: boolean;
}

/** The result of joining a challenge. */
export interface Enrollment {
  challenge_id: number;
  enrolled_at: string;
}
