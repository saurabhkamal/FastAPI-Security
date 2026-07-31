export type Role = "student" | "instructor" | "admin";

export interface CourseSummary {
  id: string;
  title: string;
  description: string;
  instructor_id: string;
  instructor_name: string;
  max_seats: number;
  seats_available: number;
}

export interface Lesson {
  id: string;
  title: string;
  content: string;
}

export interface CourseDetail extends CourseSummary {
  lessons: Lesson[];
}

export interface AuditLogEntry {
  id: string;
  action: string;
  actor_email: string;
  target: string;
  timestamp: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: Role;
}
