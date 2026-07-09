"use client";

import { useState, useEffect, useRef } from "react";
import { Loader2, Send, CheckCircle2, XCircle, Clock } from "lucide-react";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const POLL_INTERVAL = 3000;

interface ProgressData {
  total_recipients: number;
  sent_count: number;
  failed_count: number;
  queued_count: number;
  is_active: boolean;
  current_recipient: string | null;
  senders: { email: string; count: number }[];
}

export default function ProgressSection({ campaignId }: { campaignId: string }) {
  const [data, setData] = useState<ProgressData | null>(null);
  const [loading, setLoading] = useState(true);
  const { authFetch } = useApiClient();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchProgress = async () => {
    try {
      const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/send-progress`);
      if (res.ok) {
        const result = await res.json();
        setData(result);
        if (!result.is_active) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProgress();
    intervalRef.current = setInterval(fetchProgress, POLL_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [campaignId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-slate-400">
        <Loader2 className="w-4 h-4 animate-spin mr-2" />
        Loading progress...
      </div>
    );
  }

  if (!data) {
    return <div className="text-center py-16 text-sm text-slate-400">Could not load progress data.</div>;
  }

  const total = data.total_recipients || 1;
  const done = data.sent_count + data.failed_count;
  const pct = Math.round((done / total) * 100);

  return (
    <div className="space-y-6">
      {/* Progress bar */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-slate-700">
            {data.is_active ? "Sending..." : data.sent_count > 0 ? "Complete" : "Not started"}
          </span>
          <span className="text-xs text-slate-500">{done} / {total} ({pct}%)</span>
        </div>
        <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500 flex"
            style={{ width: `${Math.min(pct, 100)}%` }}
          >
            <div className="h-full bg-green-500" style={{ width: `${(data.sent_count / done) * 100}%` }} />
            <div className="h-full bg-red-500" style={{ width: `${(data.failed_count / done) * 100}%` }} />
          </div>
        </div>
        <div className="flex gap-4 mt-1.5 text-xs text-slate-400">
          <span className="flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-green-500" />
            {data.sent_count} sent
          </span>
          <span className="flex items-center gap-1">
            <XCircle className="w-3 h-3 text-red-500" />
            {data.failed_count} failed
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-amber-500" />
            {data.queued_count} queued
          </span>
        </div>
      </div>

      {/* Current recipient */}
      {data.is_active && data.current_recipient && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
          <div className="text-xs font-semibold text-blue-700 mb-1">Currently sending to</div>
          <div className="text-sm text-blue-900 font-medium">{data.current_recipient}</div>
        </div>
      )}

      {/* Sender breakdown */}
      {data.senders.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Per sender</h3>
          <div className="space-y-1.5">
            {data.senders.map((s) => (
              <div key={s.email} className="flex items-center justify-between text-sm px-3 py-2 bg-slate-50 rounded-lg">
                <span className="text-slate-700 font-medium truncate">{s.email}</span>
                <span className="text-slate-500 text-xs">{s.count} sent</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!data.is_active && data.sent_count === 0 && (
        <div className="text-center py-8 text-sm text-slate-400">
          <Send className="w-8 h-8 mx-auto mb-2 text-slate-300" />
          No sending activity yet. Use Send options to start.
        </div>
      )}

      {!data.is_active && data.sent_count > 0 && (
        <div className="text-center py-4 text-sm text-green-600 font-semibold">
          Sending finished. {data.sent_count} of {total} sent successfully.
        </div>
      )}
    </div>
  );
}
