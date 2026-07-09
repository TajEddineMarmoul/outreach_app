"use client";

import { useState, useRef, useCallback } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

interface LogEntry {
  id: number;
  recipient_email: string;
  sender_email: string;
  subject: string;
  status: string;
  error_message: string | null;
  sent_at: string | null;
  created_at: string | null;
}

export default function LogsSection({ campaignId }: { campaignId: string }) {
  const [logs, setLogs] = useState<LogEntry[] | null>(null);
  const [loading, setLoading] = useState(false);
  const { authFetch } = useApiClient();
  const hasFetched = useRef(false);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/send-logs`);
      if (res.ok) {
        setLogs(await res.json());
        hasFetched.current = true;
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [campaignId, authFetch]);

  if (!hasFetched.current && !loading) {
    fetchLogs();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-slate-400">
        <Loader2 className="w-4 h-4 animate-spin mr-2" />
        Loading logs...
      </div>
    );
  }

  if (!logs || logs.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-sm text-slate-400 mb-4">No send logs yet.</p>
        <button
          onClick={() => { hasFetched.current = false; fetchLogs(); }}
          className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 mx-auto"
        >
          <RefreshCw className="w-3 h-3" />
          Refresh
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-400">{logs.length} log entries</span>
        <div className="flex gap-2">
          <button
            onClick={() => { hasFetched.current = false; fetchLogs(); }}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
          <button
            onClick={() => window.open(`${API_URL}/api/campaigns/${campaignId}/logs/export`, "_blank")}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            Export CSV
          </button>
        </div>
      </div>
      <div className="max-h-[calc(100vh-280px)] overflow-y-auto border border-slate-200 rounded-xl">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 sticky top-0">
            <tr className="text-left text-slate-500 font-semibold">
              <th className="px-4 py-2.5">Recipient</th>
              <th className="px-4 py-2.5">Sender</th>
              <th className="px-4 py-2.5">Subject</th>
              <th className="px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5">Sent At</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {logs.map((log) => (
              <tr key={log.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-2.5 text-slate-700 max-w-[200px] truncate">{log.recipient_email}</td>
                <td className="px-4 py-2.5 text-slate-500">{log.sender_email || "-"}</td>
                <td className="px-4 py-2.5 text-slate-600 max-w-[250px] truncate">{log.subject}</td>
                <td className="px-4 py-2.5">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                    log.status === "sent" ? "bg-green-50 text-green-700" :
                    log.status === "test_sent" ? "bg-blue-50 text-blue-700" :
                    log.status === "failed" ? "bg-red-50 text-red-700" :
                    "bg-slate-100 text-slate-600"
                  }`}>
                    {log.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-slate-400">
                  {log.sent_at ? new Date(log.sent_at).toLocaleString() : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
