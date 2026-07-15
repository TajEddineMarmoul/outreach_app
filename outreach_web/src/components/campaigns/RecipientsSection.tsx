"use client";

import { Fragment, useEffect, useState } from "react";
import useSWR from "swr";
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
} from "lucide-react";
import { useApiClient } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

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
  rejected: "Recipient is not eligible for delivery",
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
  readOnly = false,
}: {
  campaignId: string;
  onOpenImport: () => void;
  readOnly?: boolean;
}) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [expandedRecipients, setExpandedRecipients] = useState<Set<number>>(new Set());
  const { authFetch } = useApiClient();

  const { data, isLoading, mutate } = useSWR<RecipientsResponse>(
    `${API_URL}/api/campaigns/${campaignId}/recipients?search=${encodeURIComponent(debouncedSearch)}&page=${page}&page_size=${RECIPIENTS_PAGE_SIZE}`,
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

  const handleReset = async (contactId: number) => {
    if (!confirm("Reset this recipient to Approved? This will remove any queued jobs.")) return;
    setActionLoading(contactId);
    try {
      const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/recipients/${contactId}/reset`, {
        method: "PATCH",
      });
      if (!res.ok) throw new Error("Reset failed");
      await mutate();
    } catch {
      alert("Failed to reset recipient");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (contactId: number) => {
    if (!confirm("Remove this recipient from the campaign? This cannot be undone.")) return;
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-slate-400">
        <Loader2 className="w-4 h-4 animate-spin mr-2" />
        Loading recipients...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            placeholder="Search by email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9 text-sm"
          />
        </div>
        <Button size="sm" className="gap-1.5" onClick={onOpenImport} disabled={readOnly}>
          <UserPlus className="w-4 h-4" />
          Add recipients
        </Button>
      </div>

      {!data || data.items.length === 0 ? (
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
                            {canReset && (
                              <button
                                onClick={() => handleReset(r.contact_id)}
                                disabled={readOnly || actionLoading === r.contact_id}
                                className="p-1.5 rounded hover:bg-slate-200 text-slate-500 hover:text-blue-600 disabled:opacity-40"
                                title="Reset to Approved"
                              >
                                <RotateCcw className="w-4 h-4" />
                              </button>
                            )}
                            <button
                              onClick={() => handleDelete(r.contact_id)}
                              disabled={readOnly || actionLoading === r.contact_id}
                              className="p-1.5 rounded hover:bg-slate-200 text-slate-500 hover:text-red-600 disabled:opacity-40"
                              title="Remove from campaign"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
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
    </div>
  );
}
