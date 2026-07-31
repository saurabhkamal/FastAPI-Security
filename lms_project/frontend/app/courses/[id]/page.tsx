"use client";

import { use, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CourseDetail } from "@/lib/types";

export default function CourseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { session } = useAuth();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enrollMessage, setEnrollMessage] = useState<string | null>(null);
  const [enrolling, setEnrolling] = useState(false);

  function loadCourse() {
    apiFetch<CourseDetail>(`/courses/${id}`)
      .then(setCourse)
      .catch((err: ApiError) => setError(err.message));
  }

  useEffect(loadCourse, [id]);

  async function handleEnroll() {
    if (!session) return;
    setEnrolling(true);
    setEnrollMessage(null);
    try {
      await apiFetch(`/courses/${id}/enroll`, { method: "POST", token: session.token });
      setEnrollMessage("Enrolled successfully!");
      loadCourse();
    } catch (err) {
      setEnrollMessage(err instanceof ApiError ? err.message : "Enrollment failed");
    } finally {
      setEnrolling(false);
    }
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!course) return <p className="text-sm text-zinc-500">Loading course...</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{course.title}</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">{course.description}</p>
        <p className="mt-2 text-sm text-zinc-500">
          Instructor: {course.instructor_name} &middot; {course.seats_available}/{course.max_seats} seats available
        </p>
      </div>

      {session?.role === "student" && (
        <div>
          <button
            onClick={handleEnroll}
            disabled={enrolling || course.seats_available === 0}
            className="rounded-full bg-foreground px-4 py-2 text-background hover:bg-[#383838] disabled:opacity-50 dark:hover:bg-[#ccc]"
          >
            {course.seats_available === 0 ? "Course full" : enrolling ? "Enrolling..." : "Enroll"}
          </button>
          {enrollMessage && <p className="mt-2 text-sm">{enrollMessage}</p>}
        </div>
      )}
      {!session && <p className="text-sm text-zinc-500">Log in as a student to enroll in this course.</p>}

      <div>
        <h2 className="text-lg font-medium">Lessons</h2>
        {course.lessons.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">No lessons published yet.</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-3">
            {course.lessons.map((lesson) => (
              <li key={lesson.id} className="rounded-lg border border-black/10 p-3 dark:border-white/10">
                <h3 className="font-medium">{lesson.title}</h3>
                <p className="mt-1 text-sm text-zinc-500">{lesson.content}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
