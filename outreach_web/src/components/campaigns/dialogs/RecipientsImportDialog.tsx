"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle, Link as LinkIcon, Loader2, Upload } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApiClient } from "@/lib/api";

type Method = "paste" | "csv" | "sheet";
interface ImportPreview {
  columns: string[];
  rows: Record<string, string>[];
  total_rows: number;
  email_column: string;
}
interface Props {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  onImported: () => Promise<void>;
}

export default function RecipientsImportDialog(props: Props) {
  return props.isOpen ? <ImportForm {...props} /> : null;
}

function ImportForm({ onClose, campaignId, onImported }: Props) {
  const { API_URL, authFetch } = useApiClient();
  const [method, setMethod] = useState<Method>("paste");
  const [raw, setRaw] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [tabName, setTabName] = useState("");
  const [sheetTabs, setSheetTabs] = useState<Array<{ title: string; gid?: string | null }>>([]);
  const [tabsLoading, setTabsLoading] = useState(false);
  const [tabsError, setTabsError] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [complete, setComplete] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (method !== "sheet" || !url.trim()) return;
    const controller = new AbortController();
    const timeout = window.setTimeout(async () => {
      setTabsLoading(true);
      setTabsError("");
      try {
        const response = await authFetch(`${API_URL}/api/google-sheets/public-tabs?url=${encodeURIComponent(url.trim())}`, { signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error("Could not list the sheet tabs. Preview will try the tab in your link.");
        if (controller.signal.aborted) return;
        const tabs = Array.isArray(data.tabs) ? data.tabs : [];
        setSheetTabs(tabs);
        // Keep the URL's gid as the default rather than silently selecting a different tab.
        setTabName("");
      } catch (err) {
        if (!controller.signal.aborted) setTabsError(err instanceof Error ? err.message : "Could not load sheet tabs.");
      } finally {
        if (!controller.signal.aborted) setTabsLoading(false);
      }
    }, 500);
    return () => { window.clearTimeout(timeout); controller.abort(); };
  }, [url, method, API_URL, authFetch]);

  const ready = method === "paste" ? Boolean(raw.trim()) : method === "csv" ? Boolean(file) : Boolean(url.trim());

  const submit = async (isPreview: boolean) => {
    if (busy || !ready || (!isPreview && !preview)) return;
    setBusy(true);
    setError("");
    try {
      const suffix = method === "sheet" ? "google-sheet" : method;
      const options: RequestInit = { method: "POST" };
      if (method === "csv") {
        const form = new FormData();
        form.append("file", file!);
        if (!isPreview) form.append("mapping_json", "{}");
        options.body = form;
      } else {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(method === "paste" ? { raw } : { url: url.trim(), tab_name: tabName, header_row: 1, mapping: {} });
      }
      const response = await authFetch(`${API_URL}/api/campaigns/${campaignId}/recipients/${isPreview ? "preview/" : ""}${suffix}`, options);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "The import could not be read. Check your data and try again.");
      if (isPreview) {
        setPreview(data as ImportPreview);
      } else {
        setComplete(Number(data.attached || 0));
        try {
          await onImported();
        } catch {
          setError("Contacts were imported, but the audience could not refresh. Reload the page to see the updated list.");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not import contacts. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !busy) onClose(); }}>
      <DialogContent className="campaign-ui campaign-import-dialog">
        <DialogHeader>
          <DialogTitle>{complete !== null ? "Import complete" : preview ? "Review your contacts" : "Import contacts"}</DialogTitle>
          <DialogDescription className="sr-only">Import contacts from pasted rows, a CSV file, or a Google Sheets link. Review before importing. No email will be sent.</DialogDescription>
        </DialogHeader>
        {complete !== null ? (
          <div className="campaign-import-complete">
            <CheckCircle size={32} />
            <h2>{complete > 0 ? `${complete} ${complete === 1 ? "contact added" : "contacts added"}` : "No new contacts to add"}</h2>
            <p>{complete > 0 ? "Your audience is ready to review. No email has been sent." : "These contacts are already in this campaign or have no email address."}</p>
          </div>
        ) : preview ? (
          <div className="campaign-import-review">
            <p><strong>{preview.total_rows} {preview.total_rows === 1 ? "row" : "rows"} found.</strong> Nothing has been imported yet.</p>
            <div className="campaign-import-table" tabIndex={0} aria-label="Contact import preview">
              <table><thead><tr>{preview.columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.columns.map((column) => <td key={column}>{row[column] || "—"}</td>)}</tr>)}</tbody></table>
            </div>
            <p className="campaign-import-hint">{preview.total_rows > preview.rows.length ? `Showing the first ${preview.rows.length} rows. ` : ""}Extra columns are kept as fields for your message.</p>
            <p className="campaign-import-hint">Duplicate emails and rows without an email are skipped.</p>
          </div>
        ) : (
          <Tabs value={method} onValueChange={(value) => { setMethod(value as Method); setError(""); }}>
            <TabsList className="campaign-import-tabs">
              <TabsTrigger value="paste" disabled={busy}>Paste rows</TabsTrigger>
              <TabsTrigger value="csv" disabled={busy}>Upload CSV</TabsTrigger>
              <TabsTrigger value="sheet" disabled={busy}>Google Sheets</TabsTrigger>
            </TabsList>
            <TabsContent value="paste" className="campaign-import-method">
              <p>Copy rows from your spreadsheet, including the header row.</p>
              <HeaderHint />
              <label className="sr-only" htmlFor="import-pasted-rows">Paste contact rows</label>
              <textarea id="import-pasted-rows" value={raw} onChange={(event) => setRaw(event.target.value)} placeholder={"email,skill,region\nalex@example.com,Design,London\nsam@example.com,Engineering,Paris"} spellCheck={false} disabled={busy} />
              <p className="campaign-import-hint">Extra columns become fields you can use in your message.</p>
            </TabsContent>
            <TabsContent value="csv" className="campaign-import-method">
              <p>Choose a CSV exported from your spreadsheet.</p>
              <HeaderHint />
              <label className="campaign-import-upload"><Upload size={28} /><strong>{file ? file.name : "Choose a CSV file"}</strong><span>CSV files up to 20 MB</span><input type="file" accept=".csv,text/csv" aria-label="Choose a CSV file" disabled={busy} onChange={(event) => { setFile(event.target.files?.[0] || null); setError(""); }} /></label>
            </TabsContent>
            <TabsContent value="sheet" className="campaign-import-method">
              <p>Paste a link to your Google Sheet.</p>
              <label className="campaign-import-field" htmlFor="import-sheet-link">Google Sheets link</label>
              <div className="campaign-import-link"><LinkIcon size={18} /><input id="import-sheet-link" type="url" value={url} placeholder="https://docs.google.com/spreadsheets/d/…" onChange={(event) => { setUrl(event.target.value); setSheetTabs([]); setTabName(""); setTabsError(""); setTabsLoading(false); }} disabled={busy} /></div>
              <HeaderHint />
              {tabsLoading && <p className="campaign-import-hint" role="status">Reading sheet tabs…</p>}
              {sheetTabs.length > 1 && <label className="campaign-import-field">Sheet tab<select value={tabName} onChange={(event) => setTabName(event.target.value)} disabled={busy}><option value="">Tab from your link</option>{sheetTabs.map((tab) => <option key={`${tab.title}-${tab.gid || ""}`} value={tab.title}>{tab.title}</option>)}</select></label>}
              {tabsError && <p className="campaign-import-hint">{tabsError}</p>}
              <p className="campaign-import-hint">If access is restricted, use Upload CSV or Paste rows.</p>
            </TabsContent>
          </Tabs>
        )}
        {error && <p className="campaign-inline-error" role="alert">{error}</p>}
        <div className="campaign-import-footer">
          <p>{complete !== null ? "No email has been sent." : preview ? "No email will be sent." : "You will review the list before importing."}</p>
          <div>
            {complete !== null ? <button className="campaign-button is-primary" onClick={onClose} disabled={busy}>Done</button> : <>
              <button className="campaign-button is-quiet" disabled={busy} onClick={() => { if (preview) { setPreview(null); setError(""); } else onClose(); }}>{preview ? <><ArrowLeft size={16} /> Back</> : "Cancel"}</button>
              <button className="campaign-button is-primary" disabled={busy || !ready} onClick={() => void submit(!preview)}>{busy ? <><Loader2 size={17} className="animate-spin" /> {preview ? "Importing…" : "Reading…"}</> : preview ? "Import contacts" : <>Preview import <ArrowRight size={17} /></>}</button>
            </>}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function HeaderHint() {
  return <div className="campaign-import-header-hint"><p>The first row must include a column named <strong>email</strong>.</p><p>Other columns are optional. Use any names you need.</p></div>;
}
