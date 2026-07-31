"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CourseSummary } from "@/lib/types";

export default function AdminDashboard() {
  const { session } = useAuth();
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  function loadCourses() {
    apiFetch<CourseSummary[]>("/courses")
      .then(setCourses)
      .catch((err: ApiError) => setError(err.message));
  }

  useEffect(loadCourses, []);

  async function handleDelete(courseId: string) {
    if (!session) return;
    setDeletingId(courseId);
    setError(null);
    try {
      await apiFetch(`/courses/${courseId}`, { method: "DELETE", token: session.token });
      loadCourses();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete course");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">All courses</h1>
        <Link href="/admin/audit-logs" className="text-sm underline">
          View audit logs
        </Link>
      </div>
      <p className="text-sm text-zinc-500">
        Admins can delete any course. New courses are created by instructors from their dashboard
        (an admin can also create one via the API by supplying an instructor_id - see the README).
      </p>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {courses.length === 0 && <p className="text-sm text-zinc-500">No courses yet.</p>}
      <div className="flex flex-col gap-3">
        {courses.map((course) => (
          <div
            key={course.id}
            className="flex items-center justify-between rounded-lg border border-black/10 p-4 dark:border-white/10"
          >
            <div>
              <h2 className="font-medium">{course.title}</h2>
              <p className="text-sm text-zinc-500">
                Instructor: {course.instructor_name} &middot; {course.seats_available}/{course.max_seats} seats
              </p>
            </div>
            <button
              onClick={() => handleDelete(course.id)}
              disabled={deletingId === course.id}
              className="rounded-full border border-red-300 px-3 py-1 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:hover:bg-red-950"
            >
              {deletingId === course.id ? "Deleting..." : "Delete"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
