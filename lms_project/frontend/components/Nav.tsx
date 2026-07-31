"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function Nav() {
  const { session, logout, loading } = useAuth();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.push("/");
  }

  return (
    <header className="border-b border-black/10 dark:border-white/10">
      <nav className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-semibold">
          LMS
        </Link>
        <div className="flex items-center gap-4 text-sm">
          <Link href="/" className="hover:underline">
            Courses
          </Link>
          {loading ? null : session ? (
            <>
              <Link href="/dashboard" className="hover:underline">
                Dashboard
              </Link>
              {session.role === "admin" && (
                <Link href="/admin/audit-logs" className="hover:underline">
                  Audit Logs
                </Link>
              )}
              <span className="text-zinc-500">
                {session.email} ({session.role})
              </span>
              <button
                onClick={handleLogout}
                className="rounded-full border border-black/10 px-3 py-1 hover:bg-black/[.04] dark:border-white/10 dark:hover:bg-white/[.08]"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="hover:underline">
                Log in
              </Link>
              <Link
                href="/register"
                className="rounded-full bg-foreground px-3 py-1 text-background hover:bg-[#383838] dark:hover:bg-[#ccc]"
              >
                Register
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
