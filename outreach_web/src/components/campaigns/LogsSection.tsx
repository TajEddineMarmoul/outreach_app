"use client";

import { useState } from "react";
import useSWR from "swr";
import { ChevronLeft, ChevronRight, Clock, Loader2, PauseCircle, RefreshCw, Send } from "lucide-react";
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

interface LogsResponse { items: LogEntry[]; total: number; page: number; page_size: number; pages: number; }
interface CampaignState {
  campaign_status: string;
  is_sending: boolean;
  is_waiting: boolean;
  next_batch_at: string | null;
  pause_reason: string | null;
}

export default function LogsSection({ campaignId }: { campaignId: string }) {
  const [page, setPage] = useState(1);
  const { data, isLoading, mutate } = useSWR<LogsResponse>(
    `${API_URL}/api/campaigns/${campaignId}/send-logs?page=${page}&page_size=10`
  );
  const { data: state, mutate: mutateState } = useSWR<CampaignState>(
    `${API_URL}/api/campaigns/${campaignId}/send-progress`,
    { refreshInterval: 3000 }
  );
  const { authFetch } = useApiClient();

  const exportLogs = async () => {
    const response = await authFetch(`${API_URL}/api/campaigns/${campaignId}/logs/export`);
    if (!response.ok) return;
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = `campaign_${campaignId}_send_log.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-slate-400">
        <Loader2 className="w-4 h-4 animate-spin mr-2" />
        Loading logs...
      </div>
    );
  }

  const logs = data?.items || [];
  const refresh = () => Promise.all([mutate(), mutateState()]);

  if (logs.length === 0 && !state?.is_waiting && !state?.is_sending && state?.campaign_status !== "paused") {
    return (
      <div className="text-center py-16">
        <p className="text-sm text-slate-400 mb-4">No send logs yet.</p>
        <button
          onClick={() => void refresh()}
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
      {state && (state.is_sending || state.is_waiting || state.campaign_status === "paused") && (
        <div className={`flex items-start gap-3 mb-4 px-4 py-3 border rounded-lg ${state.campaign_status === "paused" ? "border-amber-200 bg-amber-50 text-amber-800" : "border-blue-200 bg-blue-50 text-blue-800"}`}>
          {state.is_sending ? <Send className="w-4 h-4 mt-0.5 shrink-0" /> : state.campaign_status === "paused" ? <PauseCircle className="w-4 h-4 mt-0.5 shrink-0" /> : <Clock className="w-4 h-4 mt-0.5 shrink-0" />}
          <div>
            <div className="text-sm font-semibold">
              {state.is_sending ? "Sending a batch now" : state.campaign_status === "paused" ? "Campaign paused" : "Waiting for the next batch"}
            </div>
            <div className="text-xs mt-0.5 opacity-80">
              {state.campaign_status === "paused"
                ? state.pause_reason === "daily_caps_reached" ? "All senders reached today's daily cap." : "Sending will continue after the campaign is resumed."
                : state.next_batch_at ? `Next batch: ${new Date(state.next_batch_at).toLocaleString()}` : "The worker is checking for due work."}
            </div>
          </div>
        </div>
      )}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-400">{data?.total || 0} delivery entries</span>
        <div className="flex gap-2">
          <button
            onClick={() => void refresh()}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
          <button
            onClick={() => void exportLogs()}
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
      {(data?.pages || 1) > 1 && (
        <div className="flex items-center justify-end gap-2 mt-3">
          <button aria-label="Previous log page" title="Previous page" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="p-1.5 border border-slate-200 rounded-md disabled:opacity-40 hover:bg-slate-50">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-xs text-slate-500">Page {page} of {data?.pages || 1}</span>
          <button aria-label="Next log page" title="Next page" disabled={page >= (data?.pages || 1)} onClick={() => setPage((value) => value + 1)} className="p-1.5 border border-slate-200 rounded-md disabled:opacity-40 hover:bg-slate-50">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
