"use client";

import { Fragment, useEffect, useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Loader2,
  Search,
  Trash2,
  RotateCcw,
  UserPlus,
  EllipsisVertical,
  Upload,
} from "lucide-react";
import { useApiClient } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const RECIPIENTS_PAGE_SIZE = 10;

interface RecipientEntry {
  contact_id: number;
  email: string;
  custom_fields: Record<string, unknown>;
  status: string;
  source_type: string;
  created_at: string | null;
}

interface RecipientsResponse {
  items: RecipientEntry[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

const STATUS_BADGES: Record<string, string> = {
  approved: "bg-green-100 text-green-700",
  queued: "bg-blue-100 text-blue-700",
  sent: "bg-slate-100 text-slate-600",
  failed: "bg-red-100 text-red-700",
  rejected: "bg-amber-100 text-amber-700",
  pending: "bg-amber-100 text-amber-700",
};

const STATUS_LABELS: Record<string, string> = {
  approved: "Ready",
  queued: "Waiting to send",
  sent: "Sent",
  failed: "Failed",
  rejected: "Skipped",
  pending: "Ready",
};

const STATUS_DESCRIPTIONS: Record<string, string> = {
  approved: "Ready for a future sending batch",
  queued: "Reserved for the delivery worker; no email has been sent yet",
  sent: "Email sent successfully",
  failed: "Delivery failed and can be retried",
  rejected: "Skipped before sending because required data was missing or the recipient was otherwise ineligible",
  pending: "Ready for a future sending batch",
};

function displayFieldName(name: string): string {
  return name.trim();
}

function displayFieldValue(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function recipientFields(customFields: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(customFields).flatMap(([name, rawValue]) => {
    const normalizedName = name.trim().replace(/[\s_-]+/g, "_").toLowerCase();
    const value = displayFieldValue(rawValue);
    if (!value || ["email", "email_address", "work_email"].includes(normalizedName)) return [];
    return [[displayFieldName(name), value]];
  });
}

export default function RecipientsSection({
  campaignId,
  onOpenImport,
  onAudienceChange,
  readOnly = false,
}: {
  campaignId: string;
  onOpenImport: () => void;
  onAudienceChange?: () => Promise<void> | void;
  readOnly?: boolean;
}) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [expandedRecipients, setExpandedRecipients] = useState<Set<number>>(new Set());
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [rowMenu, setRowMenu] = useState<number | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [clearOpen, setClearOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState("");
  const [notice, setNotice] = useState("");
  const { authFetch } = useApiClient();
  const { mutate: mutateCache } = useSWRConfig();
  const recipientsUrl = `${API_URL}/api/campaigns/${campaignId}/recipients`;

  const { data, isLoading, error, mutate } = useSWR<RecipientsResponse>(
    `${recipientsUrl}?search=${encodeURIComponent(debouncedSearch)}&page=${page}&page_size=${RECIPIENTS_PAGE_SIZE}`,
    { refreshInterval: 0 }
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
      setExpandedRecipients(new Set());
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const goToPage = (nextPage: number) => {
    setPage(nextPage);
    setExpandedRecipients(new Set());
  };

  const refreshAudience = async () => {
    const refreshed = await Promise.allSettled([
      mutateCache((key) => typeof key === "string" && key.startsWith(`${recipientsUrl}?`)),
      Promise.resolve().then(() => onAudienceChange?.()),
    ]);
    if (refreshed.some((result) => result.status === "rejected")) {
      setNotice("Your change was saved, but the list could not refresh. Reload the page to see the latest audience.");
    }
  };

  const responseError = async (response: Response, fallback: string) => {
    const payload = await response.json().catch(() => null);
    return new Error(typeof payload?.detail === "string" ? payload.detail : fallback);
  };

  const handleAdd = async () => {
    if (readOnly || busy) return;
    setBusy(true);
    setDialogError("");
    try {
      const response = await authFetch(`${recipientsUrl}/one`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), first_name: firstName.trim(), company: company.trim() }),
      });
      if (!response.ok) throw await responseError(response, "Could not add this recipient. Please try again.");
      const result = await response.json();
      setNotice(result.attached > 0 ? "Recipient added to this campaign." : "This recipient is already in the campaign.");
      setAddOpen(false);
      setEmail("");
      setFirstName("");
      setCompany("");
      setSearch("");
      setDebouncedSearch("");
      goToPage(1);
      await refreshAudience();
    } catch (error) {
      setDialogError(error instanceof Error ? error.message : "Could not add this recipient.");
    } finally {
      setBusy(false);
    }
  };

  const handleClear = async () => {
    if (readOnly || busy) return;
    setBusy(true);
    setDialogError("");
    try {
      const response = await authFetch(recipientsUrl, { method: "DELETE" });
      if (!response.ok) throw await responseError(response, "Could not clear the audience. Please try again.");
      setNotice("Audience cleared. You can add recipients to start again.");
      setClearOpen(false);
      setSearch("");
      setDebouncedSearch("");
      goToPage(1);
      await mutateCache(
        (key) => typeof key === "string" && key.startsWith(`${recipientsUrl}?`),
        { items: [], total: 0, page: 1, page_size: RECIPIENTS_PAGE_SIZE, pages: 1 },
        { revalidate: false },
      );
      await refreshAudience();
    } catch (error) {
      setDialogError(error instanceof Error ? error.message : "Could not clear the audience.");
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async (contactId: number) => {
    setRowMenu(null);
    if (readOnly || busy) return;
    if (!confirm("Reset this recipient to Approved? This will remove any queued jobs.")) return;
    setActionLoading(contactId);
    try {
      const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/recipients/${contactId}/reset`, {
        method: "PATCH",
      });
      if (!res.ok) throw new Error("Reset failed");
      await refreshAudience();
    } catch {
      alert("Failed to reset recipient");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (contactId: number) => {
    setRowMenu(null);
    if (readOnly || busy) return;
    if (!confirm("Remove this recipient from the campaign? Their saved contact will be kept.")) return;
    setActionLoading(contactId);
    try {
      const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/recipients/${contactId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Delete failed");
      const updated = await mutate();
      if (updated && updated.items.length === 0 && page > 1) {
        goToPage(page - 1);
      }
      await refreshAudience();
    } catch {
      alert("Failed to delete recipient");
    } finally {
      setActionLoading(null);
    }
  };

  const toggleDetails = (contactId: number) => {
    setExpandedRecipients((current) => {
      const next = new Set(current);
      if (next.has(contactId)) next.delete(contactId);
      else next.add(contactId);
      return next;
    });
  };

  return (
    <div className="space-y-4">
      <div className="campaign-audience-toolbar">
        <div className="relative campaign-audience-search">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            placeholder="Search by email..."
            aria-label="Search recipients by email"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9 text-sm"
          />
        </div>
        <div className="campaign-audience-actions">
          <Popover open={addMenuOpen} onOpenChange={setAddMenuOpen}>
            <PopoverTrigger className="campaign-button is-primary" disabled={readOnly || busy}>
              <UserPlus size={18} /> Add recipients <ChevronDown size={15} />
            </PopoverTrigger>
            <PopoverContent align="end" className="campaign-ui campaign-more-menu">
              <button onClick={() => { setAddMenuOpen(false); setDialogError(""); setAddOpen(true); }}><UserPlus size={18} /> Add one person</button>
              <button onClick={() => { setAddMenuOpen(false); onOpenImport(); }}><Upload size={18} /> Import a list</button>
            </PopoverContent>
          </Popover>
          <Popover open={moreMenuOpen} onOpenChange={setMoreMenuOpen}>
            <PopoverTrigger className="campaign-icon-button" aria-label="Audience actions" disabled={readOnly || busy || actionLoading !== null}>
              <EllipsisVertical size={20} />
            </PopoverTrigger>
            <PopoverContent align="end" className="campaign-ui campaign-more-menu">
              <button className="is-danger" disabled={!debouncedSearch && !data?.total} onClick={() => { setMoreMenuOpen(false); setDialogError(""); setClearOpen(true); }}><Trash2 size={18} /> Clear audience</button>
            </PopoverContent>
          </Popover>
        </div>
      </div>
      {notice && <p className="campaign-audience-notice" role="status">{notice}</p>}
      {error ? (
        <div className="campaign-inline-error" role="alert">Could not load recipients. <button className="campaign-text-button" onClick={() => mutate()}>Try again</button></div>
      ) : isLoading ? (
        <div className="flex items-center justify-center py-16 text-sm text-slate-500"><Loader2 className="w-4 h-4 animate-spin mr-2" /> Loading recipients…</div>
      ) : !data || data.items.length === 0 ? (
        <div className="text-center py-12 text-sm text-slate-400">
          {debouncedSearch ? "No recipients match your search." : "No recipients yet. Add some to get started."}
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-4 text-sm text-slate-500">
            <span>
              Showing {(data.page - 1) * data.page_size + 1}-{Math.min(data.page * data.page_size, data.total)} of {data.total}
            </span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                onClick={() => goToPage(Math.max(1, data.page - 1))}
                disabled={data.page <= 1}
                title="Previous page"
                aria-label="Previous page"
              >
                <ChevronLeft />
              </Button>
              <span className="min-w-24 text-center font-medium text-slate-700">
                Page {data.page} of {data.pages}
              </span>
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                onClick={() => goToPage(Math.min(data.pages, data.page + 1))}
                disabled={data.page >= data.pages}
                title="Next page"
                aria-label="Next page"
              >
                <ChevronRight />
              </Button>
            </div>
          </div>

          <div className="border rounded-lg overflow-x-auto">
            <table className="w-full min-w-[760px] table-fixed text-sm">
              <thead>
                <tr className="bg-slate-50 border-b">
                  <th className="w-[36%] text-left px-4 py-2.5 font-semibold text-slate-600">Email</th>
                  <th className="text-left px-4 py-2.5 font-semibold text-slate-600">Details</th>
                  <th className="text-left px-4 py-2.5 font-semibold text-slate-600 w-24">Status</th>
                  <th className="text-right px-4 py-2.5 font-semibold text-slate-600 w-24">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => {
                  const fields = recipientFields(r.custom_fields || {});
                  const preview = fields.slice(0, 2).map(([name, value]) => `${name}: ${value}`).join(" · ");
                  const isExpanded = expandedRecipients.has(r.contact_id);
                  const canReset = ["sent", "failed"].includes(r.status);
                  return (
                    <Fragment key={r.contact_id}>
                      <tr className="border-b hover:bg-slate-50">
                        <td className="px-4 py-2.5">
                          <div className="font-medium text-slate-800">{r.email}</div>
                        </td>
                        <td className="px-4 py-2.5 text-slate-500 max-w-0">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="truncate" title={preview}>{preview || "No additional fields"}</span>
                            {fields.length > 2 && <span className="shrink-0 text-xs text-slate-400">+{fields.length - 2}</span>}
                          </div>
                        </td>
                        <td className="px-4 py-2.5">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGES[r.status] || "bg-slate-100 text-slate-600"}`}
                            title={STATUS_DESCRIPTIONS[r.status] || r.status}
                          >
                            {STATUS_LABELS[r.status] || r.status}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          <div className="flex items-center justify-end gap-1">
                            {fields.length > 0 && (
                              <button
                                onClick={() => toggleDetails(r.contact_id)}
                                className="p-1.5 rounded hover:bg-slate-200 text-slate-500 hover:text-slate-800"
                                title={isExpanded ? "Hide recipient fields" : "View all recipient fields"}
                                aria-expanded={isExpanded}
                              >
                                {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                              </button>
                            )}
                            <Popover open={rowMenu === r.contact_id} onOpenChange={(open) => setRowMenu(open ? r.contact_id : null)}>
                              <PopoverTrigger className="campaign-icon-button" aria-label={`Actions for ${r.email}`} disabled={readOnly || busy || actionLoading !== null}>
                                {actionLoading === r.contact_id ? <Loader2 className="animate-spin" size={16} /> : <EllipsisVertical size={16} />}
                              </PopoverTrigger>
                              <PopoverContent align="end" className="campaign-ui campaign-more-menu">
                                {canReset && <button onClick={() => handleReset(r.contact_id)}><RotateCcw size={18} /> Reset to ready</button>}
                                <button className="is-danger" onClick={() => handleDelete(r.contact_id)}><Trash2 size={18} /> Remove from campaign</button>
                              </PopoverContent>
                            </Popover>
                          </div>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="border-b bg-slate-50/70">
                          <td colSpan={4} className="px-4 py-3">
                            <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2 xl:grid-cols-3 max-h-72 overflow-y-auto pr-2">
                              {fields.map(([name, value]) => (
                                <div key={name} className="min-w-0">
                                  <dt className="text-xs font-semibold text-slate-500">{name}</dt>
                                  <dd className="text-sm text-slate-800 whitespace-pre-wrap break-words">{value}</dd>
                                </div>
                              ))}
                            </dl>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
      <Dialog open={addOpen} onOpenChange={(open) => { if (!busy) setAddOpen(open); }}>
        <DialogContent className="campaign-ui campaign-audience-dialog">
          <DialogHeader><DialogTitle>Add one person</DialogTitle><DialogDescription>No email will be sent. If this contact is already saved, their existing details will be kept.</DialogDescription></DialogHeader>
          <form className="campaign-person-form" onSubmit={(event) => { event.preventDefault(); void handleAdd(); }}>
            <label>Email address<input type="email" autoComplete="off" required value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy} /></label>
            <label>First name <span>(optional)</span><input autoComplete="off" maxLength={200} value={firstName} onChange={(event) => setFirstName(event.target.value)} disabled={busy} /></label>
            <label>Company <span>(optional)</span><input autoComplete="off" maxLength={200} value={company} onChange={(event) => setCompany(event.target.value)} disabled={busy} /></label>
            {dialogError && <p className="campaign-inline-error" role="alert">{dialogError}</p>}
            <div className="campaign-dialog-actions"><button type="button" className="campaign-button is-quiet" disabled={busy} onClick={() => setAddOpen(false)}>Cancel</button><button type="submit" className="campaign-button is-primary" disabled={busy || !email.trim()}>{busy ? "Adding…" : "Add recipient"}</button></div>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog open={clearOpen} onOpenChange={(open) => { if (!busy) setClearOpen(open); }}>
        <DialogContent className="campaign-ui campaign-audience-dialog">
          <DialogHeader><DialogTitle>Clear this campaign’s audience?</DialogTitle><DialogDescription>This removes every recipient from this campaign, including people on other pages or outside your search. Your saved contacts, message, attachments, schedule, and sending history will be kept.</DialogDescription></DialogHeader>
          <p>You will need to add recipients again before launching.</p>
          {dialogError && <p className="campaign-inline-error" role="alert">{dialogError}</p>}
          <div className="campaign-dialog-actions"><button className="campaign-button is-quiet" disabled={busy} onClick={() => setClearOpen(false)}>Cancel</button><button className="campaign-button is-danger" disabled={busy} onClick={handleClear}>{busy ? "Clearing…" : "Clear audience"}</button></div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
