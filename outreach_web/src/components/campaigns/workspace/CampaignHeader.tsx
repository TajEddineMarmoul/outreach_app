"use client";

import Link from "next/link";
import { UserButton } from "@clerk/nextjs";
import { ArrowLeft } from "lucide-react";
import AppMenu from "@/components/AppMenu";

export default function CampaignHeader({
  name,
  status,
  saveLabel,
  readOnly,
  onNameChange,
  onNameSave,
  onNavigate,
}: {
  name: string;
  status: string;
  saveLabel: string;
  readOnly: boolean;
  onNameChange: (value: string) => void;
  onNameSave: (value: string) => void;
  onNavigate: (href: string) => Promise<void>;
}) {
  const running = ["sending", "autopilot", "active"].includes(status);
  const statusLabel = running
    ? "Running"
    : status === "ended"
      ? "Completed"
      : status.charAt(0).toUpperCase() + status.slice(1);
  const navigate = (
    event: React.MouseEvent<HTMLAnchorElement>,
    href: string,
  ) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
      return;
    event.preventDefault();
    void onNavigate(href);
  };
  return (
    <header className="campaign-header">
      <Link
        href="/campaigns"
        className="campaign-brand"
        onClick={(event) => navigate(event, "/campaigns")}
      >
        OUTREACH
      </Link>
      <AppMenu onNavigate={onNavigate} />
      <Link
        href="/campaigns"
        className="campaign-back-link"
        aria-label="All campaigns"
        onClick={(event) => navigate(event, "/campaigns")}
      >
        <ArrowLeft size={21} />
        <span>All campaigns</span>
      </Link>
      <div className="campaign-identity">
        <input
          aria-label="Campaign name"
          maxLength={240}
          value={name}
          readOnly={readOnly}
          onChange={(event) => onNameChange(event.target.value)}
          onBlur={(event) => onNameSave(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
          }}
          title={name}
        />
        <span
          className={`campaign-status ${running ? "is-running" : status === "paused" || status === "draft" ? "is-draft" : ""}`}
        >
          {statusLabel}
        </span>
        <span className="campaign-save-status" role="status">
          {saveLabel}
        </span>
      </div>
      <div className="campaign-header-tools">
        <UserButton
          appearance={{ elements: { avatarBox: { width: 36, height: 36 } } }}
        />
      </div>
    </header>
  );
}
