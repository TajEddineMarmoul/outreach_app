"use client";

import useSWR from "swr";
import {
  CalendarDays,
  Clock3,
  Globe2,
  CircleCheck,
  Pause,
  Mail,
  AlertCircle,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { formatViewerWindow } from "@/lib/timezones";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export interface CampaignProgress {
  campaign_status: string;
  timezone: string;
  total_recipients: number;
  sent_count: number;
  failed_count: number;
  skipped_count: number;
  queued_count: number;
  is_active: boolean;
  is_sending: boolean;
  is_waiting: boolean;
  next_batch_at: string | null;
  current_recipient: string | null;
  pause_reason: string | null;
  dry_run: boolean;
  send_mode?: string;
  autopilot_schedule:
    { day: string; cap: number; start: string; end: string }[] | null;
}
export interface ScheduleSummary {
  timezone?: string;
  autopilot_schedule?: {
    day: string;
    cap: number;
    start: string;
    end: string;
  }[];
  send_settings?: {
    mode?: string;
    delay_minutes?: number;
    draft_scheduled_at?: string;
    dry_run?: boolean;
  };
}

function displayTime(value: string) {
  const [hour, minute] = value.split(":").map(Number);
  return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour >= 12 ? "PM" : "AM"}`;
}

export function CurrentSchedule({
  summary,
  progress,
}: {
  summary?: ScheduleSummary;
  progress?: CampaignProgress;
}) {
  const zone = progress?.timezone || summary?.timezone || "UTC";
  const viewerZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const schedule =
    progress?.autopilot_schedule || summary?.autopilot_schedule || [];
  const mode = progress?.send_mode || summary?.send_settings?.mode;
  const uniform =
    schedule.length > 0 &&
    schedule.every(
      (day) => day.start === schedule[0].start && day.end === schedule[0].end,
    );
  const isWeekdays =
    schedule.length === 5 &&
    ["monday", "tuesday", "wednesday", "thursday", "friday"].every((day) =>
      schedule.some((item) => item.day === day),
    );
  const conversion =
    mode === "autopilot" && uniform && zone !== viewerZone
      ? formatViewerWindow(schedule[0].start, schedule[0].end, zone, viewerZone)
      : null;
  const paused = progress?.campaign_status === "paused";
  const stopped = ["stopped", "ended", "completed"].includes(
    progress?.campaign_status || "",
  );
  const stateTitle = paused
    ? "Sending is paused"
    : stopped
      ? "Sending has ended"
      : progress?.dry_run
        ? "Test mode is active"
        : progress?.is_active
          ? mode === "autopilot"
            ? "Autopilot is running"
            : "Campaign is running"
          : "Schedule saved";
  const next = progress?.next_batch_at
    ? new Date(progress.next_batch_at).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : null;
  const reason =
    progress?.pause_reason === "campaign_daily_cap_reached"
      ? "Today's campaign limit has been reached."
      : progress?.pause_reason === "daily_caps_reached"
        ? "All senders have reached today's limit."
        : null;
  return (
    <section className="campaign-panel campaign-schedule-card">
      <h2>Current schedule</h2>
      <div className="campaign-schedule-lines">
        <p>
          <CalendarDays />
          <span>
            {mode === "autopilot" && schedule.length
              ? isWeekdays
                ? "Mon–Fri"
                : schedule.map((day) => day.day.slice(0, 3)).join(", ")
              : mode === "schedule"
                ? "Scheduled send"
                : mode === "send_now"
                  ? "Send when launched"
                  : "Not set yet"}
          </span>
        </p>
        {mode === "autopilot" && uniform && (
          <p>
            <Clock3 />
            <span>
              {displayTime(schedule[0].start)}–{displayTime(schedule[0].end)}
            </span>
          </p>
        )}
        {mode === "autopilot" &&
          !uniform &&
          schedule.map((day) => (
            <p key={day.day}>
              <Clock3 />
              <span className="capitalize">
                {day.day.slice(0, 3)} · {displayTime(day.start)}–
                {displayTime(day.end)}
              </span>
            </p>
          ))}
        {mode === "schedule" && summary?.send_settings?.draft_scheduled_at && (
          <p>
            <Clock3 />
            <span>
              {new Date(
                summary.send_settings.draft_scheduled_at,
              ).toLocaleString(undefined, {
                timeZone: zone,
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </span>
          </p>
        )}
        <p>
          <Globe2 />
          <span>{zone}</span>
        </p>
        {conversion && (
          <p className="campaign-local-time">
            <Clock3 />
            <span>
              {conversion.range} in{" "}
              {viewerZone.split("/").pop()?.replaceAll("_", " ")}
              <small>{conversion.date}</small>
            </span>
          </p>
        )}
      </div>
      {progress && (
        <div
          className={`campaign-schedule-state ${paused || stopped ? "is-paused" : ""}`}
        >
          {paused ? (
            <Pause size={25} />
          ) : stopped ? (
            <CircleCheck size={25} />
          ) : (
            <CircleCheck size={30} />
          )}
          <div>
            <strong>{stateTitle}</strong>
            <p>
              {paused
                ? "Resume when you're ready. No new emails will start."
                : stopped
                  ? "Your delivery history is preserved."
                  : progress.is_sending
                    ? "Sending the current batch"
                    : reason ||
                      (next
                        ? `Next check: ${next}`
                        : "Waiting for the next eligible batch")}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

export default function CampaignOverview({
  campaignId,
  summary,
  onActivity,
}: {
  campaignId: string;
  summary?: ScheduleSummary;
  onActivity: () => void;
}) {
  const {
    data: progress,
    error,
    isLoading,
  } = useSWR<CampaignProgress>(
    `${API_URL}/api/campaigns/${campaignId}/send-progress`,
    { refreshInterval: 3000 },
  );
  const { data: recipients, error: recipientsError } = useSWR<{
    items: {
      contact_id: number;
      email: string;
      custom_fields: Record<string, unknown>;
      status: string;
    }[];
  }>(
    `${API_URL}/api/campaigns/${campaignId}/recipients?page=1&page_size=3&pending_only=true`,
    { refreshInterval: 3000 },
  );
  const { data: logs, error: logsError } = useSWR<{
    items: {
      id: number;
      status: string;
      recipient_email: string;
      sent_at: string | null;
      created_at: string | null;
    }[];
  }>(`${API_URL}/api/campaigns/${campaignId}/send-logs?page=1&page_size=3`, {
    refreshInterval: 3000,
  });
  if (isLoading)
    return (
      <div className="campaign-empty">
        <Loader2 className="animate-spin" />
        Loading campaign progress…
      </div>
    );
  if (error || !progress)
    return (
      <div className="campaign-notice is-error" role="alert">
        Could not load campaign progress. Refresh the page to try again.
      </div>
    );
  const remaining = Math.max(
    0,
    progress.total_recipients -
      progress.sent_count -
      progress.failed_count -
      progress.skipped_count,
  );
  const stats = [
    { value: progress.sent_count, label: "sent", style: "is-blue" },
    { value: progress.skipped_count, label: "skipped", style: "is-muted" },
    { value: progress.failed_count, label: "failed", style: "is-red" },
    { value: remaining, label: "remaining", style: "" },
  ];
  return (
    <>
      {progress.dry_run && (
        <div className="campaign-notice">
          Test mode is active. No real emails are being sent.
        </div>
      )}
      <div className="campaign-overview-grid">
        <dl className="campaign-stats">
          {stats.map((stat) => (
            <div key={stat.label}>
              <dd className={stat.style}>{stat.value}</dd>
              <dt>{stat.label}</dt>
            </div>
          ))}
        </dl>
        <section className="campaign-panel campaign-progress-card">
          <div className="campaign-progress-heading">
            <h2>Sending progress</h2>
            <p className="campaign-progress-label">
              {progress.sent_count} of {progress.total_recipients} sent
            </p>
          </div>
          <div
            className="campaign-progress-track"
            role="progressbar"
            aria-label="Emails sent"
            aria-valuenow={progress.sent_count}
            aria-valuemin={0}
            aria-valuemax={Math.max(progress.total_recipients, 1)}
          >
            <span
              style={{
                width: `${Math.min(100, (progress.sent_count / Math.max(1, progress.total_recipients)) * 100)}%`,
              }}
            />
          </div>
          <div className="campaign-upcoming-table">
            <table>
              <thead>
                <tr>
                  <th>Upcoming recipients</th>
                  <th>Company</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {recipients?.items.map((recipient, index) => {
                  const fields = recipient.custom_fields;
                  const name = String(
                    fields.full_name || fields.first_name || recipient.email,
                  );
                  const initials = name
                    .split(/[\s@.]+/)
                    .slice(0, 2)
                    .map((part) => part[0])
                    .join("")
                    .toUpperCase();
                  return (
                    <tr key={recipient.contact_id}>
                      <td>
                        <span className={`campaign-avatar avatar-${index}`}>
                          {initials}
                        </span>
                        <span>{name}</span>
                      </td>
                      <td>
                        {String(fields.company || fields.company_name || "—")}
                      </td>
                      <td>
                        {progress.campaign_status === "paused"
                          ? "Paused"
                          : recipient.status === "queued"
                            ? "Queued"
                            : "Ready"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!recipients?.items.length && (
            <p className="campaign-table-empty">
              {recipientsError
                ? "Could not load upcoming recipients."
                : !recipients
                  ? "Loading recipients…"
                  : "No recipients waiting to send."}
            </p>
          )}
        </section>
        <CurrentSchedule summary={summary} progress={progress} />
      </div>
      <section className="campaign-panel campaign-recent-activity">
        <div className="campaign-panel-heading">
          <h2>Recent activity</h2>
          <button className="campaign-text-button" onClick={onActivity}>
            View all <ArrowRight size={16} />
          </button>
        </div>
        {logs?.items.map((log) => (
          <div key={log.id} className="campaign-activity-row">
            {log.status === "failed" ? (
              <AlertCircle className="is-red" />
            ) : (
              <Mail className="is-blue" />
            )}
            <span>
              {log.status === "failed"
                ? "Delivery failed for"
                : log.status === "test_sent"
                  ? "Test recorded for"
                  : "Email sent to"}{" "}
              {log.recipient_email}
            </span>
            <time dateTime={log.sent_at || log.created_at || undefined}>
              {log.sent_at || log.created_at
                ? new Date(log.sent_at || log.created_at!).toLocaleTimeString(
                    undefined,
                    { hour: "numeric", minute: "2-digit" },
                  )
                : "—"}
            </time>
          </div>
        ))}
        {!logs?.items.length && (
          <p className="campaign-table-empty">
            {logsError
              ? "Could not load recent activity."
              : !logs
                ? "Loading activity…"
                : "Delivery activity will appear here once sending begins."}
          </p>
        )}
      </section>
    </>
  );
}
