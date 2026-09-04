"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { AlertTriangle, Bot, CheckCircle2, Clock, Loader2, MailX, MessageSquareReply, PauseCircle, Send, Timer, XCircle } from "lucide-react";
import { API_URL } from "@/lib/api";

const POLL_INTERVAL = 3000;

interface ProgressData {
  campaign_status: string;
  timezone: string;
  total_recipients: number;
  sent_count: number;
  replied_count: number;
  automated_response_count: number;
  bounced_count: number;
  send_error_count: number;
  failed_count: number;
  skipped_count: number;
  queued_count: number;
  is_active: boolean;
  is_sending: boolean;
  is_waiting: boolean;
  current_recipient: string | null;
  next_batch_at: string | null;
  delay_minutes: number;
  pacing_mode: "fixed_delay" | "spread_evenly";
  pause_reason: string | null;
  campaign_daily_cap: number | null;
  campaign_sent_today: number | null;
  autopilot_schedule: { day: string; cap: number; start: string; end: string }[] | null;
  dry_run: boolean;
  gmail_tracking: {
    enabled: boolean;
    reconnect_required: boolean;
    setup_required: boolean;
    last_checked_at: string | null;
    error: string | null;
  };
  recipient_validation: {
    checked_recipient_count: number;
    ready_recipient_count: number;
    skipped_recipient_count: number;
    overlap_recipient_count: number;
    missing_by_variable: Array<{ variable: string; row_count: number }>;
  } | null;
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
  const days = Math.floor(remainingSeconds / 86_400);
  const hours = Math.floor((remainingSeconds % 86_400) / 3_600);
  const minutes = Math.floor((remainingSeconds % 3_600) / 60);
  const seconds = remainingSeconds % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m ${seconds}s`;
}

export default function ProgressSection({ campaignId }: { campaignId: string }) {
  const [now, setNow] = useState(() => Date.now());
  const { data, isLoading } = useSWR<ProgressData>(
    `${API_URL}/api/campaigns/${campaignId}/send-progress`,
    { refreshInterval: (latest) => latest?.is_active ? POLL_INTERVAL : 30000 }
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
  const done = data.sent_count + data.bounced_count + data.send_error_count + data.skipped_count;
  const pct = Math.round((done / Math.max(total, 1)) * 100);
  const sentWidth = done > 0 ? (data.sent_count / done) * 100 : 0;
  const bouncedWidth = done > 0 ? (data.bounced_count / done) * 100 : 0;
  const sendErrorWidth = done > 0 ? (data.send_error_count / done) * 100 : 0;
  const skippedWidth = done > 0 ? (data.skipped_count / done) * 100 : 0;
  const countdown = formatCountdown(data.next_batch_at, now);
  const isComplete = data.campaign_status === "ended" || (total > 0 && done >= total);
  const waitingReason = data.pause_reason === "campaign_daily_cap_reached"
    ? "Today's campaign limit is reached. Recipient resets do not reset real sends."
    : data.pause_reason === "daily_caps_reached"
      ? "All connected senders reached today's limit."
      : null;
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
            <div className="h-full bg-orange-500" style={{ width: `${bouncedWidth}%` }} />
            <div className="h-full bg-red-500" style={{ width: `${sendErrorWidth}%` }} />
            <div className="h-full bg-amber-400" style={{ width: `${skippedWidth}%` }} />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
          <span className="flex items-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-emerald-800"><CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />{data.sent_count} sent</span>
          <span className="flex items-center gap-1.5 rounded-md border border-orange-200 bg-orange-50 px-2.5 py-1 text-orange-800"><MailX className="h-3.5 w-3.5" aria-hidden="true" />{data.bounced_count} undelivered</span>
          <span className="flex items-center gap-1.5 rounded-md border border-rose-200 bg-rose-50 px-2.5 py-1 text-rose-800"><XCircle className="h-3.5 w-3.5" aria-hidden="true" />{data.send_error_count} send errors</span>
          <span className="flex items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-amber-800"><AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />{data.skipped_count} skipped</span>
          <span className="flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-700"><Clock className="h-3.5 w-3.5" aria-hidden="true" />{data.queued_count} queued</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
          <MessageSquareReply className="h-5 w-5 text-blue-600" aria-hidden="true" />
          <div><div className="text-xl font-semibold text-blue-900">{data.replied_count}</div><div className="text-xs font-semibold text-blue-800">Human replies</div><div className="text-xs text-blue-700">A person wrote back</div></div>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <Bot className="h-5 w-5 text-amber-600" aria-hidden="true" />
          <div><div className="text-xl font-semibold text-amber-900">{data.automated_response_count}</div><div className="text-xs font-semibold text-amber-800">Automated replies</div><div className="text-xs text-amber-700">Out-of-office or system response</div></div>
        </div>
      </div>

      {data.gmail_tracking.reconnect_required && (
        <div className="flex items-start gap-3 border border-amber-200 bg-amber-50 px-4 py-3 rounded-lg" role="status">
          <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          <div className="text-sm text-amber-900">
            Reconnect the campaign&apos;s Gmail account to count replies, automated responses, and undelivered addresses.
          </div>
        </div>
      )}

      {!data.gmail_tracking.reconnect_required && data.gmail_tracking.setup_required && !data.gmail_tracking.error && (
        <div className="flex items-start gap-3 border border-blue-200 bg-blue-50 px-4 py-3 rounded-lg" role="status">
          <Clock className="w-5 h-5 text-blue-600 mt-0.5 shrink-0" />
          <div className="text-sm text-blue-900">
            Live Gmail event tracking is being set up. New replies and undelivered emails will update automatically.
          </div>
        </div>
      )}

      {data.gmail_tracking.error && (
        <div className="border border-red-200 bg-red-50 px-4 py-3 rounded-lg text-sm text-red-800" role="alert">
          {data.gmail_tracking.error}
        </div>
      )}

      {data.recipient_validation && data.recipient_validation.skipped_recipient_count > 0 && (
        <div className="flex items-start gap-3 border border-amber-200 bg-amber-50 px-4 py-3 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          <div className="text-xs text-amber-800">
            <div className="text-sm font-semibold text-amber-900">
              {data.recipient_validation.skipped_recipient_count} recipient{data.recipient_validation.skipped_recipient_count === 1 ? " was" : "s were"} skipped before sending
            </div>
            <div className="mt-1">
              {data.recipient_validation.missing_by_variable.map((item) => (
                <span key={item.variable} className="mr-3 inline-block">
                  <code>{`{{${item.variable}}}`}</code>: {item.row_count} row{item.row_count === 1 ? "" : "s"}
                </span>
              ))}
            </div>
            {data.recipient_validation.overlap_recipient_count > 0 && (
              <div className="mt-1">
                {data.recipient_validation.overlap_recipient_count} recipient{data.recipient_validation.overlap_recipient_count === 1 ? " was" : "s were"} missing multiple values; the total above counts each recipient once.
              </div>
            )}
          </div>
        </div>
      )}

      {data.is_waiting && (
        <div className="flex items-start gap-3 border border-amber-200 bg-amber-50 px-4 py-3 rounded-lg">
          <Timer className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-amber-900">
              Waiting for the next batch{countdown ? ` - ${countdown}` : ""}
            </div>
            {waitingReason && <div className="text-xs text-amber-700 mt-0.5">{waitingReason}</div>}
            <div className="text-xs text-amber-700 mt-0.5">
              Next check: {data.next_batch_at ? new Date(data.next_batch_at).toLocaleString(undefined, { timeZoneName: "short" }) : "pending worker check"}
              {data.pacing_mode === "spread_evenly"
                ? " · spread evenly across today's window"
                : data.delay_minutes > 0
                  ? ` · ${data.delay_minutes} minute delay between batches`
                  : ""}
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
          <div className="flex items-center justify-between gap-3 mb-2">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Autopilot schedule</h3>
            <span className="text-xs text-slate-500">
              {data.pacing_mode === "spread_evenly" ? "Spread evenly" : "Fixed delay"} · {data.timezone}
            </span>
          </div>
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
                  {(data.campaign_sent_today ?? 0) >= data.campaign_daily_cap && (
                    <div className="text-xs text-blue-700 mt-1">Next eligible day required</div>
                  )}
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
          Sending finished. {data.sent_count} sent, {data.bounced_count} undelivered, {data.send_error_count} send errors, and {data.skipped_count} skipped.
        </div>
      )}
    </div>
  );
}
