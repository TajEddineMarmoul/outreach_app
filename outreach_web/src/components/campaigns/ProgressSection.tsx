"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { AlertTriangle, CheckCircle2, Clock, Loader2, PauseCircle, Send, Timer, XCircle } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const POLL_INTERVAL = 3000;

interface ProgressData {
  campaign_status: string;
  total_recipients: number;
  sent_count: number;
  failed_count: number;
  queued_count: number;
  is_active: boolean;
  is_sending: boolean;
  is_waiting: boolean;
  current_recipient: string | null;
  next_batch_at: string | null;
  delay_minutes: number;
  pause_reason: string | null;
  campaign_daily_cap: number | null;
  campaign_sent_today: number | null;
  autopilot_schedule: { day: string; cap: number; start: string; end: string }[] | null;
  dry_run: boolean;
  senders: {
    id: number;
    email: string;
    status: string;
    campaign_sent: number;
    sent_today: number;
    daily_cap: number;
    remaining_today: number;
    capacity_state: "available" | "low" | "exhausted";
    last_error: string | null;
  }[];
}

function formatCountdown(nextBatchAt: string | null, now: number) {
  if (!nextBatchAt) return null;
  const remainingSeconds = Math.max(0, Math.ceil((new Date(nextBatchAt).getTime() - now) / 1000));
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export default function ProgressSection({ campaignId }: { campaignId: string }) {
  const [now, setNow] = useState(() => Date.now());
  const { data, isLoading } = useSWR<ProgressData>(
    `${API_URL}/api/campaigns/${campaignId}/send-progress`,
    { refreshInterval: (latest) => latest?.is_active ? POLL_INTERVAL : 0 }
  );

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  if (isLoading) {
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

  const total = data.total_recipients;
  const done = data.sent_count + data.failed_count;
  const pct = Math.round((done / Math.max(total, 1)) * 100);
  const sentWidth = done > 0 ? (data.sent_count / done) * 100 : 0;
  const failedWidth = done > 0 ? (data.failed_count / done) * 100 : 0;
  const countdown = formatCountdown(data.next_batch_at, now);
  const isComplete = data.campaign_status === "ended" || (total > 0 && done >= total);
  const stateLabel = data.is_sending
    ? "Sending now"
    : data.is_waiting
      ? "Waiting for next batch"
      : data.campaign_status === "paused"
        ? "Paused"
        : data.campaign_status === "stopped"
          ? "Stopped"
          : isComplete
            ? "Complete"
            : "Not started";

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-slate-700">
            {stateLabel}
            {data.dry_run && (
              <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-purple-100 text-purple-700">
                TEST MODE
              </span>
            )}
          </span>
          <span className="text-xs text-slate-500">{done} / {total} ({pct}%)</span>
        </div>
        <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500 flex"
            style={{ width: `${Math.min(pct, 100)}%` }}
          >
            <div className="h-full bg-green-500" style={{ width: `${sentWidth}%` }} />
            <div className="h-full bg-red-500" style={{ width: `${failedWidth}%` }} />
          </div>
        </div>
        <div className="flex gap-4 mt-1.5 text-xs text-slate-400">
          <span className="flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-green-500" />{data.sent_count} sent</span>
          <span className="flex items-center gap-1"><XCircle className="w-3 h-3 text-red-500" />{data.failed_count} failed</span>
          <span className="flex items-center gap-1"><Clock className="w-3 h-3 text-amber-500" />{data.queued_count} queued</span>
        </div>
      </div>

      {data.is_waiting && (
        <div className="flex items-start gap-3 border border-amber-200 bg-amber-50 px-4 py-3 rounded-lg">
          <Timer className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-amber-900">
              Waiting for the next batch{countdown ? ` - ${countdown}` : ""}
            </div>
            <div className="text-xs text-amber-700 mt-0.5">
              Next check: {data.next_batch_at ? new Date(data.next_batch_at).toLocaleString() : "pending worker check"}
              {data.delay_minutes > 0 ? ` · ${data.delay_minutes} minute delay between batches` : ""}
            </div>
          </div>
        </div>
      )}

      {data.campaign_status === "paused" && (
        <div className="flex items-start gap-3 border border-amber-200 bg-amber-50 px-4 py-3 rounded-lg">
          <PauseCircle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-amber-900">Campaign paused</div>
            <div className="text-xs text-amber-700 mt-0.5">
              {data.pause_reason === "daily_caps_reached"
                ? "Every connected sender has reached today's limit."
                : data.pause_reason === "campaign_daily_cap_reached"
                  ? "Campaign reached its daily sending limit."
                  : "Resume the campaign when you are ready to continue."}
            </div>
          </div>
        </div>
      )}

      {data.autopilot_schedule && data.autopilot_schedule.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Autopilot schedule</h3>
          <div className="space-y-1.5">
            {data.campaign_daily_cap != null && (
              <div className="flex items-center gap-3 px-3 py-2 bg-blue-50 rounded-lg mb-2">
                <div className="flex-1">
                  <div className="flex justify-between text-sm text-slate-700 mb-1">
                    <span className="font-medium">Today</span>
                    <span>{data.campaign_sent_today ?? 0} / {data.campaign_daily_cap} used</span>
                  </div>
                  <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500 bg-blue-500"
                      style={{ width: `${Math.min(((data.campaign_sent_today ?? 0) / data.campaign_daily_cap) * 100, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            )}
            <div className="flex flex-wrap gap-1.5">
              {data.autopilot_schedule.map((s) => (
                <span
                  key={s.day}
                  className="text-xs px-2 py-1 rounded bg-slate-100 text-slate-600"
                  title={`${s.day}: ${s.cap}/day, ${s.start}-${s.end}`}
                >
                  {s.day.slice(0, 3)} {s.cap}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {data.is_active && data.current_recipient && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
          <div className="text-xs font-semibold text-blue-700 mb-1">Currently sending to</div>
          <div className="text-sm text-blue-900 font-medium">{data.current_recipient}</div>
        </div>
      )}

      {data.senders.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Per sender</h3>
          <div className="space-y-1.5">
            {data.senders.map((sender) => (
              <div key={sender.id} className="flex items-center justify-between gap-4 text-sm px-3 py-2.5 bg-slate-50 rounded-lg">
                <div className="min-w-0">
                  <div className="text-slate-700 font-medium truncate">{sender.email}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {sender.campaign_sent} this campaign · {sender.sent_today}/{sender.daily_cap} today · {sender.remaining_today} remaining
                  </div>
                  {sender.last_error && <div className="text-xs text-red-600 mt-1 truncate">{sender.last_error}</div>}
                </div>
                {sender.capacity_state !== "available" && (
                  <span className={`flex items-center gap-1 text-xs font-semibold shrink-0 ${sender.capacity_state === "exhausted" ? "text-red-600" : "text-amber-600"}`}>
                    <AlertTriangle className="w-3.5 h-3.5" />
                    {sender.capacity_state === "exhausted" ? "Daily cap reached" : "Running low"}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!data.is_active && !isComplete && !["paused", "stopped"].includes(data.campaign_status) && data.sent_count === 0 && (
        <div className="text-center py-8 text-sm text-slate-400">
          <Send className="w-8 h-8 mx-auto mb-2 text-slate-300" />
          No sending activity yet. Use Send options to start.
        </div>
      )}

      {isComplete && (
        <div className="text-center py-4 text-sm text-green-600 font-semibold">
          Sending finished. {data.sent_count} of {total} sent successfully.
        </div>
      )}
    </div>
  );
}
