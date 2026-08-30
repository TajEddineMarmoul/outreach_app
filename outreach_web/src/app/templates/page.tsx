"use client";

import { useState } from "react";
import useSWR from "swr";
import { FileText, Plus } from "lucide-react";
import { useApiClient } from "@/lib/api";
import {
  ActionMenu,
  AppDialog,
  ConfirmDialog,
  MenuAction,
  Notice,
  PageHeading,
  PageState,
  Pager,
  SearchField,
  checkResponse,
  errorMessage,
  formatDate,
} from "@/components/app-ui";

interface Template {
  id: number;
  title: string;
  subject: string;
  body: string;
  updated_at?: string;
}
const emptyTemplate = { title: "", subject: "", body: "" };
const PAGE_SIZE = 6;

export default function TemplatesPage() {
  const { API_URL, authFetch } = useApiClient();
  const {
    data: templates = [],
    error,
    isLoading,
    mutate,
  } = useSWR<Template[]>(`${API_URL}/api/templates`);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Template | "new" | null>(null);
  const [draft, setDraft] = useState(emptyTemplate);
  const [removing, setRemoving] = useState<Template | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [message, setMessage] = useState("");
  const filtered = templates.filter((item) =>
    `${item.title} ${item.subject}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const currentPage = Math.min(
    page,
    Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)),
  );
  const edit = (template: Template | "new") => {
    setEditing(template);
    setDraft(template === "new" ? emptyTemplate : template);
    setActionError("");
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setActionError("");
    try {
      const isNew = editing === "new";
      await checkResponse(
        await authFetch(
          `${API_URL}/api/templates${!isNew && editing ? `/${editing.id}` : ""}`,
          {
            method: isNew ? "POST" : "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              title: draft.title.trim(),
              subject: draft.subject,
              body: draft.body,
            }),
          },
        ),
      );
      await mutate();
      setEditing(null);
      setMessage("Template saved.");
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!removing) return;
    setBusy(true);
    setActionError("");
    try {
      await checkResponse(
        await authFetch(`${API_URL}/api/templates/${removing.id}`, {
          method: "DELETE",
        }),
      );
      await mutate();
      setRemoving(null);
      setMessage("Template removed. Campaign messages are unchanged.");
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="app-page">
      <PageHeading
        title="Templates"
        description="Reusable starting points for your emails."
        actions={
          <button className="app-button is-primary" onClick={() => edit("new")}>
            <Plus size={18} /> New template
          </button>
        }
      />
      <Notice message={message} />
      <div className="app-toolbar">
        <SearchField
          label="Search templates"
          value={search}
          onChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
        />
      </div>
      <div className="app-table-wrap">
        <PageState
          loading={isLoading}
          error={error}
          empty={!filtered.length}
          retry={() => void mutate()}
        >
          {templates.length ? undefined : (
            <>
              <h2>Save a starting point</h2>
              <p>
                Create a template to reuse your subject and message in a
                campaign.
              </p>
            </>
          )}
        </PageState>
        {!isLoading && !error && filtered.length > 0 && (
          <table className="app-table">
            <thead>
              <tr>
                <th scope="col">Template</th>
                <th scope="col">Subject</th>
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
                      <button
                        className="app-name app-name-button"
                        onClick={() => edit(item)}
                      >
                        <FileText size={19} color="#506184" />
                        {item.title}
                      </button>
                    </td>
                    <td>{item.subject}</td>
                    <td className="app-muted">{formatDate(item.updated_at)}</td>
                    <td>
                      <ActionMenu iconOnly label={`Actions for ${item.title}`}>
                        <MenuAction onClick={() => edit(item)}>
                          Edit template
                        </MenuAction>
                        <MenuAction
                          danger
                          onClick={() => {
                            setRemoving(item);
                            setActionError("");
                          }}
                        >
                          Delete template
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
        open={editing !== null}
        onClose={() => {
          if (!busy) setEditing(null);
        }}
        title={editing === "new" ? "New template" : "Edit template"}
        description="This is a reusable template. Saving it does not send an email or change existing campaigns."
      >
        <form className="app-form" onSubmit={save}>
          <label className="app-field">
            Template name
            <input
              autoFocus
              required
              maxLength={240}
              value={draft.title}
              onChange={(event) =>
                setDraft({ ...draft, title: event.target.value })
              }
            />
          </label>
          <label className="app-field">
            Subject
            <input
              required
              maxLength={998}
              value={draft.subject}
              onChange={(event) =>
                setDraft({ ...draft, subject: event.target.value })
              }
            />
          </label>
          <label className="app-field">
            Message
            <textarea
              aria-label="Message"
              aria-describedby="template-message-hint"
              required
              value={draft.body}
              onChange={(event) =>
                setDraft({ ...draft, body: event.target.value })
              }
            />
            <small id="template-message-hint">
              Personalize with variables such as {"{{first_name}}"}. HTML is
              preserved if your template already uses it.
            </small>
          </label>
          <Notice error={actionError} />
          <div className="app-dialog-actions">
            <button
              type="button"
              className="app-button"
              disabled={busy}
              onClick={() => setEditing(null)}
            >
              Cancel
            </button>
            <button
              className="app-button is-primary"
              disabled={
                busy ||
                !draft.title.trim() ||
                !draft.subject.trim() ||
                !draft.body.trim()
              }
            >
              {busy ? "Saving…" : "Save template"}
            </button>
          </div>
        </form>
      </AppDialog>
      <ConfirmDialog
        open={!!removing}
        title="Delete template?"
        description={`Delete “${removing?.title}”? Existing campaign messages will stay unchanged.`}
        busy={busy}
        error={actionError}
        onClose={() => setRemoving(null)}
        onConfirm={() => void remove()}
        label="Delete template"
      />
    </div>
  );
}
