"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CourseSummary } from "@/lib/types";

export default function StudentDashboard() {
  const { session } = useAuth();
  const [courses, setCourses] = useState<CourseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    apiFetch<CourseSummary[]>(`/students/${session.userId}/courses`, { token: session.token })
      .then(setCourses)
      .catch((err: ApiError) => setError(err.message));
  }, [session]);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">My courses</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!courses && !error && <p className="text-sm text-zinc-500">Loading...</p>}
      {courses && courses.length === 0 && (
        <p className="text-sm text-zinc-500">
          You are not enrolled in any courses yet. Browse the{" "}
          <Link href="/" className="underline">
            course catalog
          </Link>
          .
        </p>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {courses?.map((course) => (
          <Link
            key={course.id}
            href={`/courses/${course.id}`}
            className="rounded-lg border border-black/10 p-4 hover:bg-black/[.03] dark:border-white/10 dark:hover:bg-white/[.05]"
          >
            <h2 className="font-medium">{course.title}</h2>
            <p className="mt-1 text-sm text-zinc-500">Instructor: {course.instructor_name}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
