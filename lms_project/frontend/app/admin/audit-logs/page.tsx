"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AuditLogEntry } from "@/lib/types";

export default function AuditLogsPage() {
  const { session, loading } = useAuth();
  const router = useRouter();
  const [logs, setLogs] = useState<AuditLogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!session || session.role !== "admin") {
      router.push("/");
      return;
    }
    apiFetch<AuditLogEntry[]>("/admin/audit-logs", { token: session.token })
      .then(setLogs)
      .catch((err: ApiError) => setError(err.message));
  }, [session, loading, router]);

  if (loading || !session || session.role !== "admin") return null;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Audit logs</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!logs && !error && <p className="text-sm text-zinc-500">Loading...</p>}
      {logs && logs.length === 0 && <p className="text-sm text-zinc-500">No audit events yet.</p>}
      {logs && logs.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-black/10 dark:border-white/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-black/[.03] dark:bg-white/[.06]">
              <tr>
                <th className="px-4 py-2">Action</th>
                <th className="px-4 py-2">Actor</th>
                <th className="px-4 py-2">Target</th>
                <th className="px-4 py-2">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-t border-black/10 dark:border-white/10">
                  <td className="px-4 py-2">{log.action}</td>
                  <td className="px-4 py-2">{log.actor_email}</td>
                  <td className="px-4 py-2 font-mono text-xs">{log.target}</td>
                  <td className="px-4 py-2">{new Date(log.timestamp).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
