"use client";

import { type ReactNode } from "react";
import { Menu } from "@base-ui/react/menu";
import {
  Ban,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CircleDashed,
  Clock3,
  EllipsisVertical,
  Loader2,
  MailX,
  MessageSquareReply,
  PauseCircle,
  Search,
  type LucideIcon,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

export function PageHeading({
  title,
  description,
  actions,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="app-heading">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="app-actions">{actions}</div>}
    </div>
  );
}

export function ActionMenu({
  label = "More",
  children,
  primary = false,
  iconOnly = false,
  disabled = false,
}: {
  label?: string;
  children: ReactNode;
  primary?: boolean;
  iconOnly?: boolean;
  disabled?: boolean;
}) {
  return (
    <Menu.Root>
      <Menu.Trigger
        disabled={disabled}
        aria-label={label}
        className={`app-button ${primary ? "is-primary" : ""} ${iconOnly ? "is-icon is-quiet" : ""}`}
      >
        {iconOnly ? (
          <EllipsisVertical size={19} />
        ) : (
          <>
            {label}
            {label === "More" ? (
              <EllipsisVertical size={18} />
            ) : (
              <ChevronDown size={17} />
            )}
          </>
        )}
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner
          className="app-menu-positioner"
          align="end"
          sideOffset={6}
        >
          <Menu.Popup className="app-ui app-menu">{children}</Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}

export function MenuAction({
  children,
  onClick,
  danger,
  disabled,
}: {
  children: ReactNode;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <Menu.Item
      className={`app-menu-item ${danger ? "is-danger" : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </Menu.Item>
  );
}

export function SearchField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="app-search">
      <Search size={18} aria-hidden="true" />
      <input
        type="search"
        aria-label={label}
        placeholder={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export function PageState({
  loading,
  error,
  empty,
  children,
  retry,
}: {
  loading?: boolean;
  error?: unknown;
  empty?: boolean;
  children?: ReactNode;
  retry?: () => void;
}) {
  if (loading)
    return (
      <div className="app-empty" role="status">
        <Loader2 size={22} className="animate-spin" />
        Loading…
      </div>
    );
  if (error)
    return (
      <div className="app-empty" role="alert">
        <p>We couldn’t load this page. Please try again.</p>
        {retry && (
          <button className="app-button" onClick={retry}>
            Try again
          </button>
        )}
      </div>
    );
  if (empty)
    return (
      <div className="app-empty">
        {children || "No results found. Try another search or filter."}
      </div>
    );
  return null;
}

export function Notice({
  error,
  message,
}: {
  error?: string;
  message?: string;
}) {
  if (!error && !message) return null;
  return (
    <p
      className={`app-notice ${error ? "is-error" : ""}`}
      role={error ? "alert" : "status"}
    >
      {error || message}
    </p>
  );
}

export function Pager({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  return (
    <div className="app-pager">
      <span>
        {total
          ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`
          : "0 results"}
      </span>
      <div className="app-actions">
        <button
          className="app-button is-icon"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft size={18} />
        </button>
        <span>
          Page {page} of {Math.max(1, Math.ceil(total / pageSize))}
        </span>
        <button
          className="app-button is-icon"
          aria-label="Next page"
          disabled={page * pageSize >= total}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}

const STATUS_LABELS: Record<string, string> = {
  sending: "Running",
  autopilot: "Running",
  ended: "Completed",
  sent: "Sent",
  success: "Sent",
  bounced: "Undelivered",
  failed: "Send error",
  error: "Send error",
  replied: "Human reply",
  automated_response: "Automated reply",
  do_not_contact: "Do not contact",
  rejected: "Skipped",
  approved: "Ready",
  ready: "Ready",
  queued: "Waiting to send",
  test_sent: "Test sent",
};

const STATUS_ICONS: Record<string, LucideIcon> = {
  connected: CheckCircle2,
  approved: CheckCircle2,
  ready: CheckCircle2,
  sending: CheckCircle2,
  autopilot: CheckCircle2,
  ended: CheckCircle2,
  sent: CheckCircle2,
  success: CheckCircle2,
  test_sent: CheckCircle2,
  replied: MessageSquareReply,
  automated_response: Bot,
  bounced: MailX,
  failed: CircleAlert,
  error: CircleAlert,
  revoked: CircleAlert,
  queued: Clock3,
  scheduled: Clock3,
  pending: Clock3,
  paused: PauseCircle,
  do_not_contact: Ban,
  rejected: Ban,
};

export function StatusBadge({ status, title }: { status: string; title?: string }) {
  const Icon = STATUS_ICONS[status] || CircleDashed;
  return (
    <span className={`app-status status-${status}`} title={title}>
      <Icon size={13} strokeWidth={2.2} aria-hidden="true" />
      {STATUS_LABELS[status] ||
        status.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase())}
    </span>
  );
}

export function AppDialog({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
    >
      <DialogContent className="app-ui app-dialog">
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription className={description ? "app-muted" : "sr-only"}>
          {description || title}
        </DialogDescription>
        {children}
      </DialogContent>
    </Dialog>
  );
}

export function ConfirmDialog({
  open,
  title,
  description,
  busy,
  error,
  onClose,
  onConfirm,
  label = "Remove",
}: {
  open: boolean;
  title: string;
  description: string;
  busy: boolean;
  error?: string;
  onClose: () => void;
  onConfirm: () => void;
  label?: string;
}) {
  return (
    <AppDialog
      open={open}
      title={title}
      description={description}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <Notice error={error} />
      <div className="app-dialog-actions">
        <button className="app-button" disabled={busy} onClick={onClose}>
          Cancel
        </button>
        <button
          className="app-button is-danger"
          disabled={busy}
          onClick={onConfirm}
        >
          {busy ? "Please wait…" : label}
        </button>
      </div>
    </AppDialog>
  );
}

export function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(
    /[zZ]$|[+-]\d{2}:?\d{2}$/.test(value)
      ? value
      : `${value.replace(" ", "T")}Z`,
  );
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
}

export function downloadCsv(
  filename: string,
  rows: (string | number | null | undefined)[][],
) {
  const csv = rows
    .map((row) =>
      row
        .map((cell) => {
          let value = String(cell ?? "");
          if (/^[\s]*[=+@-]/.test(value)) value = `'${value}`;
          return `"${value.replaceAll('"', '""')}"`;
        })
        .join(","),
    )
    .join("\r\n");
  const url = URL.createObjectURL(
    new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
