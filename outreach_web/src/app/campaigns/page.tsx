"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { Plus } from "lucide-react";
import { useApiClient } from "@/lib/api";
import {
  ActionMenu,
  AppDialog,
  MenuAction,
  Notice,
  PageHeading,
  Pager,
  PageState,
  SearchField,
  StatusBadge,
  checkResponse,
  errorMessage,
  formatDate,
} from "@/components/app-ui";

interface Campaign {
  id: number;
  name: string;
  status: string;
  recipient_count: number;
  sent_count: number;
  updated_at?: string;
}
const PAGE_SIZE = 6;

export default function CampaignsPage() {
  return <Suspense fallback={<div className="app-page">Loading campaigns…</div>}><CampaignsContent /></Suspense>;
}

function CampaignsContent() {
  const { API_URL, authFetch } = useApiClient();
  const {
    data: campaigns = [],
    error,
    isLoading,
    mutate,
  } = useSWR<Campaign[]>(`${API_URL}/api/campaigns`);
  const router = useRouter();
  const searchParams = useSearchParams();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const fromWelcome = searchParams.get("create") === "1";
  const createOpen = open || fromWelcome;
  const closeCreate = () => {
    if (busy) return;
    setOpen(false);
    if (fromWelcome) router.replace("/campaigns", { scroll: false });
  };
  const filtered = campaigns.filter(
    (item) =>
      item.name.toLowerCase().includes(search.toLowerCase()) &&
      (!status ||
        (status === "running"
          ? ["sending", "autopilot"].includes(item.status)
          : item.status === status)),
  );
  const currentPage = Math.min(
    page,
    Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)),
  );
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setActionError("");
    try {
      const created = await checkResponse(
        await authFetch(`${API_URL}/api/campaigns`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name.trim() }),
        }),
      );
      await mutate();
      setOpen(false);
      setName("");
      router.push(`/campaigns/${created.id}?step=audience`);
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  const duplicate = async (id: number) => {
    setBusy(true);
    setActionError("");
    try {
      const copy = await checkResponse(
        await authFetch(`${API_URL}/api/campaigns/${id}/duplicate`, {
          method: "POST",
        }),
      );
      await mutate();
      router.push(`/campaigns/${copy.id}?step=audience`);
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="app-page">
      <PageHeading
        title="Campaigns"
        description="Create, review, and manage your campaigns."
        actions={
          <button
            className="app-button is-primary"
            onClick={() => {
              setActionError("");
              setOpen(true);
            }}
          >
            <Plus size={18} /> New campaign
          </button>
        }
      />
      {!createOpen && <Notice error={actionError} />}
      <div className="app-toolbar">
        <SearchField
          label="Search campaigns"
          value={search}
          onChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
        />
        <select
          aria-label="Filter by status"
          className="app-select"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="running">Running</option>
          <option value="scheduled">Scheduled</option>
          <option value="paused">Paused</option>
          <option value="ended">Completed</option>
          <option value="stopped">Stopped</option>
          <option value="ready">Ready</option>
        </select>
      </div>
      <div className="app-table-wrap">
        <PageState
          loading={isLoading}
          error={error}
          empty={!filtered.length}
          retry={() => void mutate()}
        >
          {campaigns.length ? undefined : (
            <>
              <h2>Your next campaign starts here</h2>
              <p>Create a campaign, then choose who to reach.</p>
              <button className="app-button" onClick={() => setOpen(true)}>
                Create campaign
              </button>
            </>
          )}
        </PageState>
        {!isLoading && !error && filtered.length > 0 && (
          <table className="app-table">
            <thead>
              <tr>
                <th scope="col">Campaign</th>
                <th scope="col">Status</th>
                <th scope="col">Progress</th>
                <th scope="col">Updated</th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered
                .slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
                .map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link
                        href={`/campaigns/${item.id}`}
                        className="app-name app-name-button"
                      >
                        {item.name}
                      </Link>
                    </td>
                    <td>
                      <StatusBadge status={item.status || "draft"} />
                    </td>
                    <td>
                      {item.recipient_count ? (
                        <>
                          <span>
                            {item.sent_count ?? 0} of {item.recipient_count}{" "}
                            sent
                          </span>
                          <span className="app-progress" aria-hidden="true">
                            <span
                              style={{
                                width: `${Math.min(100, ((item.sent_count || 0) / item.recipient_count) * 100)}%`,
                              }}
                            />
                          </span>
                        </>
                      ) : (
                        <span className="app-muted">No recipients yet</span>
                      )}
                    </td>
                    <td className="app-muted">{formatDate(item.updated_at)}</td>
                    <td>
                      <ActionMenu
                        iconOnly
                        label={`Actions for ${item.name}`}
                        disabled={busy}
                      >
                        <MenuAction
                          onClick={() => router.push(`/campaigns/${item.id}`)}
                        >
                          Open campaign
                        </MenuAction>
                        <MenuAction onClick={() => void duplicate(item.id)}>
                          Duplicate campaign
                        </MenuAction>
                      </ActionMenu>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </div>
      {filtered.length > 0 && (
        <Pager
          page={currentPage}
          pageSize={PAGE_SIZE}
          total={filtered.length}
          onChange={setPage}
        />
      )}
      <AppDialog
        open={createOpen}
        onClose={closeCreate}
        title="Create campaign"
        description="Give this campaign a name you’ll recognize."
      >
        <form className="app-form" onSubmit={create}>
          <label className="app-field">
            Campaign name
            <input
              autoFocus
              required
              maxLength={240}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Fall hiring outreach"
            />
          </label>
          <Notice error={actionError} />
          <div className="app-dialog-actions">
            <button
              type="button"
              className="app-button"
              disabled={busy}
              onClick={closeCreate}
            >
              Cancel
            </button>
            <button
              className="app-button is-primary"
              disabled={busy || !name.trim()}
            >
              {busy ? "Creating…" : "Create campaign"}
            </button>
          </div>
        </form>
      </AppDialog>
    </div>
  );
}
