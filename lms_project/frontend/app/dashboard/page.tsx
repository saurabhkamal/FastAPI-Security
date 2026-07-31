"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import StudentDashboard from "./StudentDashboard";
import InstructorDashboard from "./InstructorDashboard";
import AdminDashboard from "./AdminDashboard";

export default function DashboardPage() {
  const { session, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !session) router.push("/login");
  }, [loading, session, router]);

  if (loading || !session) return <p className="text-sm text-zinc-500">Loading...</p>;

  if (session.role === "student") return <StudentDashboard />;
  if (session.role === "instructor") return <InstructorDashboard />;
  return <AdminDashboard />;
}
