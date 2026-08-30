"use client";

import {
  AlertCircle,
  CircleCheck,
  Clock3,
  Info,
  Loader2,
  Mail,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";
import type { CampaignStep } from "./CampaignSteps";
import { scheduleLabel, type ScheduleDraft } from "./scheduleDraft";

export interface RecipientValidation {
  checked_recipient_count: number;
  ready_recipient_count: number;
  skipped_recipient_count: number;
  overlap_recipient_count: number;
  missing_by_variable: { variable: string; row_count: number }[];
}
export default function CampaignReview({
  recipients,
  subject,
  senderCount,
  draft,
  configured,
  validation,
  loading,
  validationError,
  onRetry,
  messageReady,
  scheduleError,
  ready,
  onEdit,
  onTest,
  testLoading,
}: {
  recipients: number;
  subject: string;
  senderCount: number;
  draft: ScheduleDraft | null;
  configured: boolean;
  validation?: RecipientValidation;
  loading: boolean;
  validationError: boolean;
  onRetry: () => void;
  messageReady: boolean;
  scheduleError: string;
  ready: boolean;
  onEdit: (step: CampaignStep) => void;
  onTest: () => void;
  testLoading: boolean;
}) {
  const skipped = validation?.skipped_recipient_count || 0;
  const rows = [
    {
      step: "audience" as const,
      icon: Users,
      title: "Audience",
      text: validation
        ? `${validation.ready_recipient_count.toLocaleString()} people ready`
        : `${recipients.toLocaleString()} people`,
    },
    {
      step: "message" as const,
      icon: Mail,
      title: "Message",
      text: subject || "No subject yet",
    },
    {
      step: "senders" as const,
      icon: UserRound,
      title: "Senders",
      text: `${senderCount} connected ${senderCount === 1 ? "account" : "accounts"}`,
    },
    {
      step: "schedule" as const,
      icon: Clock3,
      title: "Schedule",
      text: draft && configured ? scheduleLabel(draft) : "Not set yet",
    },
  ];
  const checks = [
    {
      ok: Boolean(validation && validation.ready_recipient_count > 0),
      text: loading
        ? "Checking the audience…"
        : validationError
          ? "Could not check the audience"
          : validation?.ready_recipient_count
            ? "Audience is ready"
            : "Add recipients with complete template values",
      step: "audience" as const,
    },
    {
      ok: messageReady,
      text: messageReady
        ? "Message and personalization fields are ready"
        : "Complete your message and fix unknown fields",
      step: "message" as const,
    },
    {
      ok: senderCount > 0,
      text: senderCount
        ? `${senderCount} ${senderCount === 1 ? "sender" : "senders"} connected`
        : "Connect at least one sender",
      step: "senders" as const,
    },
    {
      ok: configured && !scheduleError,
      text: !configured
        ? "Choose your schedule"
        : scheduleError || "Schedule is valid",
      step: "schedule" as const,
    },
  ];
  const issues = checks.filter((check) => !check.ok);
  const passed = checks.filter((check) => check.ok);
  return (
    <div className="campaign-minimal-review">
      <div role="status" className={`campaign-ready-banner ${ready ? "is-ready" : "needs-attention"}`}>
        {loading ? <Loader2 className="animate-spin" /> : ready ? <CircleCheck /> : <AlertCircle />}
        <span>{loading ? "Checking your campaign…" : ready ? draft?.dryRun ? "Ready for a test run" : "Ready to launch" : "A few details need your attention"}</span>
      </div>
      <section className="campaign-review-summary" aria-label="Campaign summary">
        {rows.map((row) => (
          <div className="campaign-summary-row" key={row.step}>
            <span className="campaign-summary-icon"><row.icon /></span>
            <strong>{row.title}</strong>
            <span>{row.text}</span>
            <button className="campaign-text-button" aria-label={`Edit ${row.title.toLowerCase()}`} onClick={() => onEdit(row.step)}>Edit</button>
          </div>
        ))}
      </section>
      {issues.length > 0 && (
        <ul className="campaign-review-issues" aria-label="Items to check">
          {issues.map((check) => (
            <li key={check.step}>
              <AlertCircle className="campaign-check-warning" size={18} />
              <span>{check.text}</span>
              {!(loading && check.step === "audience") && (
                <button className="campaign-text-button" onClick={() => validationError && check.step === "audience" ? onRetry() : onEdit(check.step)}>
                  {validationError && check.step === "audience" ? "Retry" : "Fix"}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {skipped > 0 && (
        <div className="campaign-notice campaign-review-skipped" role="status">
          <Info size={18} />
          <div>
            <p>{skipped} {skipped === 1 ? "contact has" : "contacts have"} missing values and will be skipped.</p>
            <small>{validation?.missing_by_variable.filter((item) => item.row_count > 0).map((item) => `${item.variable}: ${item.row_count}`).join(" · ")}</small>
          </div>
          <button onClick={() => onEdit("audience")}>Review contacts</button>
        </div>
      )}
      <div className="campaign-review-extras">
        <details className="campaign-check-details">
          <summary>{passed.length} of {checks.length} checks passed</summary>
          <ul>{passed.map((check) => <li key={check.step}><CircleCheck size={16} /> {check.text}</li>)}</ul>
        </details>
        <button className="campaign-text-button" disabled={testLoading || !messageReady || !validation?.ready_recipient_count} onClick={onTest}>
          {testLoading ? "Opening preview…" : "Preview & test"}
        </button>
      </div>
      <p className="campaign-launch-note"><ShieldCheck size={17} /> {draft?.dryRun ? "Test mode is on. No real emails will be sent." : "Nothing sends until you launch this campaign."}</p>
    </div>
  );
}
