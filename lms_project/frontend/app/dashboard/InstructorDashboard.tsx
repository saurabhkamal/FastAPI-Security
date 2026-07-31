"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CourseSummary } from "@/lib/types";

export default function InstructorDashboard() {
  const { session } = useAuth();
  const [courses, setCourses] = useState<CourseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [maxSeats, setMaxSeats] = useState(20);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  function loadCourses() {
    apiFetch<CourseSummary[]>("/courses")
      .then((all) => setCourses(all.filter((c) => c.instructor_id === session?.userId)))
      .catch((err: ApiError) => setError(err.message));
  }

  useEffect(loadCourses, [session]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!session) return;
    setCreating(true);
    setCreateError(null);
    try {
      await apiFetch("/courses", {
        method: "POST",
        token: session.token,
        body: { title, description, max_seats: maxSeats },
      });
      setTitle("");
      setDescription("");
      setMaxSeats(20);
      loadCourses();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Could not create course");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="mb-4 text-2xl font-semibold">Create a course</h1>
        <form onSubmit={handleCreate} className="flex max-w-md flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Title
            <input
              required
              minLength={3}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="rounded-md border border-black/10 px-3 py-2 dark:border-white/10 dark:bg-black"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Description
            <textarea
              required
              minLength={10}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="rounded-md border border-black/10 px-3 py-2 dark:border-white/10 dark:bg-black"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Max seats
            <input
              type="number"
              required
              min={1}
              value={maxSeats}
              onChange={(e) => setMaxSeats(Number(e.target.value))}
              className="rounded-md border border-black/10 px-3 py-2 dark:border-white/10 dark:bg-black"
            />
          </label>
          {createError && <p className="text-sm text-red-600">{createError}</p>}
          <button
            type="submit"
            disabled={creating}
            className="rounded-full bg-foreground px-4 py-2 text-background hover:bg-[#383838] disabled:opacity-50 dark:hover:bg-[#ccc]"
          >
            {creating ? "Creating..." : "Create course"}
          </button>
        </form>
      </div>

      <div>
        <h2 className="mb-4 text-xl font-medium">My courses</h2>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {courses.length === 0 && <p className="text-sm text-zinc-500">You haven&apos;t created any courses yet.</p>}
        <div className="flex flex-col gap-4">
          {courses.map((course) => (
            <CourseLessonPanel key={course.id} course={course} onLessonAdded={loadCourses} />
          ))}
        </div>
      </div>
    </div>
  );
}

function CourseLessonPanel({ course, onLessonAdded }: { course: CourseSummary; onLessonAdded: () => void }) {
  const { session } = useAuth();
  const [lessonTitle, setLessonTitle] = useState("");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleAddLesson(e: FormEvent) {
    e.preventDefault();
    if (!session) return;
    setSubmitting(true);
    setMessage(null);
    try {
      await apiFetch(`/courses/${course.id}/lessons`, {
        method: "POST",
        token: session.token,
        body: { title: lessonTitle, content },
      });
      setLessonTitle("");
      setContent("");
      setMessage("Lesson added.");
      onLessonAdded();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Could not add lesson");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-black/10 p-4 dark:border-white/10">
      <h3 className="font-medium">{course.title}</h3>
      <p className="text-sm text-zinc-500">
        {course.seats_available}/{course.max_seats} seats available
      </p>
      <form onSubmit={handleAddLesson} className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-start">
        <input
          required
          minLength={2}
          placeholder="Lesson title"
          value={lessonTitle}
          onChange={(e) => setLessonTitle(e.target.value)}
          className="flex-1 rounded-md border border-black/10 px-3 py-2 text-sm dark:border-white/10 dark:bg-black"
        />
        <input
          required
          placeholder="Lesson content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="flex-1 rounded-md border border-black/10 px-3 py-2 text-sm dark:border-white/10 dark:bg-black"
        />
        <button
          type="submit"
          disabled={submitting}
          className="rounded-full border border-black/10 px-3 py-2 text-sm hover:bg-black/[.04] disabled:opacity-50 dark:border-white/10 dark:hover:bg-white/[.08]"
        >
          {submitting ? "Adding..." : "Add lesson"}
        </button>
      </form>
      {message && <p className="mt-2 text-sm">{message}</p>}
    </div>
  );
}
