"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { CourseSummary } from "@/lib/types";

export default function CoursesPage() {
  const [courses, setCourses] = useState<CourseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<CourseSummary[]>("/courses")
      .then(setCourses)
      .catch((err: ApiError) => setError(err.message));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Course catalog</h1>
      <p className="text-sm text-zinc-500">
        Anyone can browse the catalog. Log in as a student to enroll.
      </p>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {!courses && !error && <p className="text-sm text-zinc-500">Loading courses...</p>}
      {courses && courses.length === 0 && (
        <p className="text-sm text-zinc-500">No courses have been created yet.</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {courses?.map((course) => (
          <Link
            key={course.id}
            href={`/courses/${course.id}`}
            className="rounded-lg border border-black/10 p-4 hover:bg-black/[.03] dark:border-white/10 dark:hover:bg-white/[.05]"
          >
            <h2 className="font-medium">{course.title}</h2>
            <p className="mt-1 line-clamp-2 text-sm text-zinc-500">{course.description}</p>
            <p className="mt-2 text-xs text-zinc-400">
              Instructor: {course.instructor_name} &middot; {course.seats_available}/{course.max_seats} seats
              available
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
