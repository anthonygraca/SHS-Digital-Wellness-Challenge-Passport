export interface Session {
  subject: string;
  affiliation: string;
  isCurrentStudent: boolean;
  student_id: number; // Database ID for check-ins and enrollments (US-15)
}
