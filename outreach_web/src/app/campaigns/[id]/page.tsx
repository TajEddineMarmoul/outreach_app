"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import useSWR, { mutate } from "swr";
import {
  ArrowLeft,
  Loader2,
  Mail,
  Send,
  MoreVertical,
  Trash2,
  Paperclip,
  CheckCircle,
  AlertTriangle,
  Play,
  Pause,
  StopCircle,
  FileSpreadsheet,
  Upload,
  ClipboardList,
  Eye,
  Info,
  ExternalLink,
  Braces,
  Save,
  ChevronLeft,
  ChevronRight,
  Plus,
  Pencil,
  Check,
  X,
  ChevronDown,
  FolderPlus,
  AtSign,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import RichTextEditor from "@/components/RichTextEditor";
import ScheduleDialog from "@/components/campaigns/dialogs/ScheduleDialog";
import SenderSelectionDialog from "@/components/campaigns/dialogs/SenderSelectionDialog";
import PreviewDialog from "@/components/campaigns/dialogs/PreviewDialog";
import AttachmentDialog from "@/components/campaigns/dialogs/AttachmentDialog";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => {
  if (!r.ok) throw new Error("API call failed");
  return r.json();
});

export default function CampaignEditorPage() {
  const params = useParams();
  const router = useRouter();
  const campaignId = params.id;

  // ----------------------------------------------------
  // SWR Hooks for Data Fetching
  // ----------------------------------------------------
  const { data: campaign, error: campError, isLoading: campLoading } = useSWR(
    campaignId ? `${API_URL}/api/campaigns/${campaignId}` : null,
    fetcher
  );
  
  const { data: summary, mutate: mutateSummary } = useSWR(
    campaignId ? `${API_URL}/api/campaigns/${campaignId}/summary` : null,
    fetcher
  );

  const { data: valSummary, mutate: mutateValSummary } = useSWR(
    campaignId ? `${API_URL}/api/campaigns/${campaignId}/validation-summary` : null,
    fetcher
  );

  const { data: senders, mutate: mutateSenders } = useSWR(`${API_URL}/api/senders`, fetcher);
  const { data: oauthStatus } = useSWR(`${API_URL}/api/oauth/status`, fetcher);

  const senderCountInGroup = useMemo(() => {
    if (!summary?.sender || !senders) return 0;
    return senders.filter((s: any) => s.group_name?.trim() === summary.sender.trim()).length;
  }, [summary?.sender, senders]);

  // ----------------------------------------------------
  // UI & Form States
  // ----------------------------------------------------
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [fallback, setFallback] = useState("");
  const [requireAttachment, setRequireAttachment] = useState(false);
  const [trackingEnabled, setTrackingEnabled] = useState(true);
  const [unsubscribeLink, setUnsubscribeLink] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [showAllWarnings, setShowAllWarnings] = useState(false);

  const activeVariables = useMemo(() => {
    if (!valSummary?.all_columns?.length) return [];
    const columns = [...valSummary.all_columns];
    const hasKeywords = columns.some(col => col.startsWith("keyword_"));
    if (hasKeywords && !columns.includes("keyword_sentence")) {
      columns.push("keyword_sentence");
    }
    return columns.sort();
  }, [valSummary]);

  useEffect(() => {
    if (valSummary) {
      console.log("[valSummary] all_columns:", valSummary.all_columns);
      console.log("[valSummary] total_contacts:", valSummary.total_contacts);
    }
  }, [valSummary]);
  
  // Sync state once data loads
  useEffect(() => {
    if (campaign) {
      setName(campaign.name || "");
      setSubject(campaign.subject_template || "");
      setBody(campaign.body_template || "");
      setFallback(campaign.fallback_body_template || "");
      setRequireAttachment(campaign.require_attachment || false);
      setTrackingEnabled(campaign.tracking_enabled !== false);
      setUnsubscribeLink(campaign.unsubscribe_link !== false);
    }
  }, [campaign]);

  // Modal open states
  const [sendModalOpen, setSendModalOpen] = useState(false);
  const [sendTab, setSendTab] = useState("send-now");
  const [senderModalOpen, setSenderModalOpen] = useState(false);
  const [recipientsModalOpen, setRecipientsModalOpen] = useState(false);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [attachmentModalOpen, setAttachmentModalOpen] = useState(false);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  
  // ----------------------------------------------------
  // TipTap Editor Ref for Variable Insertion
  // ----------------------------------------------------
  const tiptapEditorRef = useRef<any>(null);

  const insertVariable = (variable: string) => {
    const editor = tiptapEditorRef.current;
    if (!editor) return;
    const placeholder = `{{ ${variable} }}`;
    editor.chain().focus().insertContent(placeholder).run();
  };

  // ----------------------------------------------------
  // Save & Actions Handlers
  // ----------------------------------------------------
  const handleSave = async () => {
    setIsSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/campaigns/${campaignId}/composer`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_template: subject,
          body_template: body,
          fallback_body_template: fallback,
          attachment_path: campaign?.attachment_path || "",
          require_attachment: requireAttachment,
        }),
      });
      if (!res.ok) throw new Error("Save draft failed");
      mutate(`${API_URL}/api/campaigns/${campaignId}`);
      mutateSummary();
      mutateValSummary();
    } catch (err: any) {
      alert(err.message || "Failed to save draft");
    } finally {
      setIsSaving(false);
    }
  };

  const handleOpenPreview = async () => {
    setIsPreviewLoading(true);
    try {
      // 1. Save draft
      const saveRes = await fetch(`${API_URL}/api/campaigns/${campaignId}/composer`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_template: subject,
          body_template: body,
          fallback_body_template: fallback,
          attachment_path: campaign?.attachment_path || "",
          require_attachment: requireAttachment,
        }),
      });
      if (!saveRes.ok) throw new Error("Failed to save draft");

      // 2. Generate previews
      const genRes = await fetch(`${API_URL}/api/campaigns/${campaignId}/preview/generate`, {
        method: "POST",
      });
      if (!genRes.ok) throw new Error("Failed to compile previews");

      // 3. Mutate SWR cache to update
      await mutate(`${API_URL}/api/campaigns/${campaignId}`);
      await mutateSummary();
      await mutateValSummary();
      await mutate(`${API_URL}/api/campaigns/${campaignId}/preview`);

      // 4. Open preview modal
      setPreviewModalOpen(true);
    } catch (err: any) {
      alert("Failed to load preview: " + err.message);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleUpdateName = async (newName: string) => {
    setName(newName);
    if (!newName.trim() || newName === campaign?.name) return;
    try {
      await fetch(`${API_URL}/api/campaigns/${campaignId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName }),
      });
      mutate(`${API_URL}/api/campaigns/${campaignId}`);
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleTracking = async (checked: boolean) => {
    setTrackingEnabled(checked);
    try {
      await fetch(`${API_URL}/api/campaigns/${campaignId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tracking_enabled: checked }),
      });
      mutate(`${API_URL}/api/campaigns/${campaignId}`);
      mutateSummary();
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleUnsubscribe = async (checked: boolean) => {
    setUnsubscribeLink(checked);
    try {
      await fetch(`${API_URL}/api/campaigns/${campaignId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ unsubscribe_link: checked }),
      });
      mutate(`${API_URL}/api/campaigns/${campaignId}`);
      mutateSummary();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteCampaign = async () => {
    if (!confirm("Are you sure you want to delete this campaign? This cannot be undone.")) return;
    try {
      await fetch(`${API_URL}/api/campaigns/${campaignId}`, { method: "DELETE" });
      router.push("/campaigns");
    } catch (err) {
      alert("Failed to delete campaign");
    }
  };

  const [connectingSender, setConnectingSender] = useState(false);

  const handleSelectSender = async (senderId: number) => {
    try {
      const res = await fetch(`${API_URL}/api/campaigns/${campaignId}/sender`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sender_id: senderId }),
      });
      if (!res.ok) throw new Error("Failed to update sender");
      mutateSummary();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleConnectSender = async () => {
    setConnectingSender(true);
    try {
      const res = await fetch(`${API_URL}/api/senders/connect`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to connect new sender");
      }
      const data = await res.json();
      await fetch(`${API_URL}/api/campaigns/${campaignId}/sender`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sender_id: data.id }),
      });
      alert(`Connected sender successfully: ${data.email}`);
      mutateSenders();
      mutateSummary();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setConnectingSender(false);
    }
  };

  const handleCampaignAction = async (action: string) => {
    try {
      const res = await fetch(`${API_URL}/api/campaigns/${campaignId}/${action}`, { method: "POST" });
      if (!res.ok) throw new Error(`Action ${action} failed`);
      mutate(`${API_URL}/api/campaigns/${campaignId}`);
      mutateSummary();
    } catch (err: any) {
      alert(err.message);
    }
  };

  if (campLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-2 h-screen">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
        <span className="text-sm">Loading campaign details...</span>
      </div>
    );
  }

  if (campError || !campaign) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-red-500 font-medium h-screen gap-4">
        <span>Failed to load campaign. Ensure backend is running.</span>
        <Button onClick={() => router.push("/campaigns")} variant="outline">
          Back to campaigns
        </Button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50/20">
      {/* ----------------------------------------------------
          1. Header Section
          ---------------------------------------------------- */}
      <header className="h-16 border-b border-slate-200 bg-white flex items-center justify-between px-8 shrink-0">
        <div className="flex items-center gap-4 flex-1">
          <Link href="/campaigns" className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500 transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={(e) => handleUpdateName(e.target.value)}
            className="font-bold text-xl text-slate-900 border-none bg-transparent hover:bg-slate-50 focus:bg-slate-100 rounded px-2 py-0.5 outline-none max-w-sm focus:ring-1 focus:ring-blue-500/20"
          />
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border bg-slate-100 text-slate-700 border-slate-200 uppercase tracking-wider scale-90">
            {campaign.status}
          </span>
          <span className="text-sm text-slate-500 flex items-center gap-1.5">
            {summary?.recipients || 0} recipients
            {summary?.sheet_synced && (
              <span title="Synced from Google Sheets" className="inline-flex items-center gap-0.5 text-blue-600 text-[10px] font-medium cursor-default">
                <Upload className="w-3 h-3" />
                sync
              </span>
            )}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="text-slate-600 gap-1.5 cursor-pointer"
            onClick={handleOpenPreview}
            disabled={isPreviewLoading}
          >
            {isPreviewLoading ? (
              <Loader2 className="w-4 h-4 animate-spin text-slate-500" />
            ) : (
              <Eye className="w-4 h-4" />
            )}
            <span>{isPreviewLoading ? "Compiling..." : "Show preview"}</span>
          </Button>

          <Button
            className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5 shadow-sm"
            onClick={() => {
              setSendTab("send-now");
              setSendModalOpen(true);
            }}
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send options</span>
          </Button>

          <Popover>
            <PopoverTrigger className="p-2 hover:bg-slate-100 rounded-lg text-slate-500 flex items-center justify-center cursor-pointer transition-colors border border-transparent">
              <MoreVertical className="w-4 h-4" />
            </PopoverTrigger>
            <PopoverContent align="end" className="w-48 p-1">
              {campaign.status === "sending" || campaign.status === "active" ? (
                <button
                  onClick={() => handleCampaignAction("pause")}
                  className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 rounded-md flex items-center gap-2"
                >
                  <Pause className="w-4 h-4 text-amber-500" />
                  <span>Pause campaign</span>
                </button>
              ) : campaign.status === "paused" ? (
                <button
                  onClick={() => handleCampaignAction("resume")}
                  className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 rounded-md flex items-center gap-2"
                >
                  <Play className="w-4 h-4 text-green-500" />
                  <span>Resume campaign</span>
                </button>
              ) : null}

              {["sending", "scheduled", "autopilot", "paused"].includes(campaign.status) ? (
                <button
                  onClick={() => handleCampaignAction("stop")}
                  className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 rounded-md flex items-center gap-2"
                >
                  <StopCircle className="w-4 h-4 text-red-500" />
                  <span>Stop campaign</span>
                </button>
              ) : null}

              <button
                onClick={() => window.open(`${API_URL}/api/campaigns/${campaignId}/logs/export`, "_blank")}
                className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 rounded-md flex items-center gap-2"
              >
                <ClipboardList className="w-4 h-4 text-slate-500" />
                <span>Export send logs</span>
              </button>

              <div className="border-t border-slate-100 my-1"></div>

              <button
                onClick={handleDeleteCampaign}
                className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-md flex items-center gap-2"
              >
                <Trash2 className="w-4 h-4" />
                <span>Delete campaign</span>
              </button>
            </PopoverContent>
          </Popover>
        </div>
      </header>

      {/* Validation Warnings Banner */}
      {valSummary && (valSummary.used_warnings.length > 0 || valSummary.other_warnings.length > 0) && (
        <div className="bg-amber-50/85 border-b border-amber-200/50 px-8 py-3 select-none flex flex-col gap-2 shrink-0 backdrop-blur-sm animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="w-4.5 h-4.5 text-amber-600 mt-0.5 shrink-0" />
              <div className="space-y-1">
                <p className="text-sm font-semibold text-amber-800">
                  Data Warning: Some recipient columns have empty values
                </p>
                {valSummary.used_warnings.length > 0 && (
                  <p className="text-xs text-amber-700 leading-normal">
                    <span className="font-semibold text-red-700">Critical (Used in Template):</span> The following variables are referenced in your email template but have empty values for some contacts:{" "}
                    {valSummary.used_warnings.map((w: any, idx: number) => (
                      <span key={w.column} className="font-semibold underline decoration-red-400">
                        {w.column} ({w.empty_count} rows){idx < valSummary.used_warnings.length - 1 ? ", " : ""}
                      </span>
                    ))}
                    . <span className="font-medium text-amber-950">You must fix these values or contacts will be blocked from approval/sending.</span>
                  </p>
                )}
                {valSummary.other_warnings.length > 0 && !showAllWarnings && (
                  <button
                    onClick={() => setShowAllWarnings(true)}
                    className="text-xs font-semibold text-amber-700 hover:text-amber-900 underline flex items-center gap-1 cursor-pointer select-none pt-0.5"
                  >
                    Show all empty columns ({valSummary.other_warnings.length} more)
                  </button>
                )}
                {valSummary.other_warnings.length > 0 && showAllWarnings && (
                  <div className="space-y-1 pt-1.5 border-t border-amber-200/40">
                    <p className="text-xs text-amber-700 leading-normal">
                      <span className="font-semibold">Other Empty Columns:</span> The following columns also contain empty values for some contacts (but are not used in your template):{" "}
                      {valSummary.other_warnings.map((w: any, idx: number) => (
                        <span key={w.column} className="font-medium text-slate-700">
                          {w.column} ({w.empty_count} rows){idx < valSummary.other_warnings.length - 1 ? ", " : ""}
                        </span>
                      ))}
                      .
                    </p>
                    <button
                      onClick={() => setShowAllWarnings(false)}
                      className="text-xs font-semibold text-amber-700 hover:text-amber-900 underline flex items-center gap-1 cursor-pointer select-none"
                    >
                      Hide other empty columns
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------
          2. Main Layout (Composer + Settings)
          ---------------------------------------------------- */}
      <div className="flex-1 flex overflow-hidden p-8 gap-8 max-w-6xl mx-auto w-full">
        {/* Left Side: Composer Card */}
        <div className="flex-1 flex flex-col gap-6 overflow-y-auto pr-2">
          <div className="space-y-4">
            {/* 1. Header Metadata fields Card */}
            <div className="bg-slate-50/70 border border-slate-200/80 rounded-t-xl p-5 space-y-4">
              {/* From Row */}
              <div className="flex items-start gap-4">
                <label className="w-16 text-sm font-semibold text-slate-500 mt-1.5">From</label>
                <div className="flex-1 flex items-center justify-between">
                  {summary?.sender ? (
                    <Button
                      variant="ghost"
                      className="p-0 h-auto text-blue-600 hover:text-blue-800 hover:bg-transparent text-sm font-medium gap-1 flex items-center justify-start"
                      onClick={() => setSenderModalOpen(true)}
                    >
                      <span>{summary.sender}</span>
                      <span className="text-xs font-normal text-slate-400 ml-1">
                        ({senderCountInGroup} sender{senderCountInGroup !== 1 ? "s" : ""})
                      </span>
                      <span className="text-slate-400 font-normal">▾</span>
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      className="p-0 h-auto text-blue-600 hover:text-blue-800 hover:bg-transparent text-sm font-semibold gap-1 flex items-center justify-start"
                      onClick={() => setSenderModalOpen(true)}
                    >
                      No sender connected. Click to Connect ▾
                    </Button>
                  )}
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={isSaving}
                    className="p-1.5 hover:bg-slate-200/60 rounded text-slate-400 hover:text-slate-600 transition-colors cursor-pointer shrink-0"
                    title="Save draft"
                  >
                    <Save className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* To Row */}
              <div className="flex items-center gap-4">
                <label className="w-16 text-sm font-semibold text-slate-500">To</label>
                <div className="flex-1">
                  <Button
                    className="bg-blue-50 hover:bg-blue-100 text-blue-600 border border-blue-200 rounded-full py-0.5 px-3.5 h-7 text-xs font-semibold"
                    onClick={() => setRecipientsModalOpen(true)}
                  >
                    {summary?.recipients ? `${summary.recipients} recipients` : "Select recipients"}
                  </Button>
                </div>
              </div>

              {/* Subject Row */}
              <div className="flex items-center gap-4 border-t border-slate-100 pt-3">
                <label className="w-16 text-sm font-semibold text-slate-500">Subject</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Enter email subject template"
                  className="flex-1 text-slate-900 border-none outline-none focus:ring-0 placeholder-slate-400 py-1 bg-transparent text-sm font-medium"
                />
              </div>
            </div>

            {/* 2. Editor Body Card with Rich Text Editor */}
            <div className="bg-white border border-t-0 border-slate-200 rounded-b-xl overflow-hidden focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100/50 transition-all flex flex-col">
              {/* Actions Toolbar */}
              <div className="flex items-center justify-between px-4 py-2 border-b border-slate-100 bg-slate-50/50 select-none">
                <div className="flex items-center gap-2">
                  {/* Add Attachment Button */}
                  <button
                    type="button"
                    className="p-1.5 hover:bg-slate-200/60 rounded text-slate-500 hover:text-slate-800 transition-colors flex items-center gap-1"
                    onClick={() => setAttachmentModalOpen(true)}
                    title="Add attachment"
                  >
                    <Paperclip className="w-4 h-4" />
                    <span className="text-xs font-semibold">Attach</span>
                  </button>

                  {/* Use Template Button */}
                  <button
                    type="button"
                    className="p-1.5 hover:bg-slate-200/60 rounded text-slate-500 hover:text-slate-800 transition-colors flex items-center gap-1"
                    onClick={() => setTemplateModalOpen(true)}
                    title="Select template"
                  >
                    <ClipboardList className="w-4 h-4" />
                    <span className="text-xs font-semibold">Template</span>
                  </button>
                </div>

                {/* Variable Insertion dropdown */}
                <Popover>
                  <PopoverTrigger className="p-1.5 hover:bg-slate-200/60 rounded text-slate-600 hover:text-slate-900 transition-colors flex items-center gap-1 cursor-pointer h-7" title="Insert variables">
                    <Braces className="w-4 h-4" />
                    <span className="text-[10px] font-bold uppercase tracking-wider">Variables</span>
                  </PopoverTrigger>
                  <PopoverContent align="end" className="w-48 max-h-64 overflow-y-auto p-1">
                    {activeVariables.length === 0 ? (
                      <p className="px-3 py-2 text-xs text-slate-400">Import contacts first</p>
                    ) : (
                      activeVariables.map((v) => (
                        <button
                          key={v}
                          onClick={() => insertVariable(v)}
                          className="w-full text-left px-3 py-1.5 text-xs hover:bg-slate-100 rounded transition-colors text-slate-700 cursor-pointer"
                        >
                          {v}
                        </button>
                      ))
                    )}
                  </PopoverContent>
                </Popover>
              </div>

              {/* TipTap Rich Text Editor */}
              <RichTextEditor
                content={body}
                onChange={setBody}
                placeholder="Compose your email or select a template..."
                onEditorReady={(editor) => { tiptapEditorRef.current = editor; }}
              />

              {/* Unknown variable warnings */}
              {(() => {
                const used = [...body.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map(m => m[1]);
                const valid = new Set(activeVariables);
                const unknown = [...new Set(used.filter(v => !valid.has(v)))];
                if (unknown.length === 0) return null;
                return (
                  <div className="mx-4 mb-3 space-y-1">
                    {unknown.map(v => (
                      <div key={v} className="flex items-center gap-1.5 text-xs text-red-600 font-medium">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                        <code className="bg-red-50 px-1 rounded">&#123;&#123; {v} &#125;&#125;</code>
                        <span className="text-red-400">not in your imported data</span>
                      </div>
                    ))}
                  </div>
                );
              })()}

              {/* Bottom attachment display chip */}
              {summary?.attachment && summary.attachment !== "none" && (
                <div className="mx-4 mb-4 p-2 bg-slate-50 border border-slate-100 rounded-lg flex items-center justify-between max-w-xs shadow-sm">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 truncate">
                    <Paperclip className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                    <span className="truncate">{summary.attachment}</span>
                  </div>
                  <button
                    onClick={async () => {
                      await fetch(`${API_URL}/api/campaigns/${campaignId}/attachment`, { method: "DELETE" });
                      mutateSummary();
                    }}
                    className="text-slate-400 hover:text-red-600 transition-colors p-1"
                    title="Remove attachment"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

            </div>

          </div>
        </div>

      </div>

      {/* ----------------------------------------------------
          3. Modals & Dialogs
          ---------------------------------------------------- */}

      {/* A. Send Campaign Modal */}
      <ScheduleDialog
        isOpen={sendModalOpen}
        onClose={() => setSendModalOpen(false)}
        campaignId={campaignId as string}
        defaultTab={sendTab}
        mutateAll={() => {
          mutate(`${API_URL}/api/campaigns/${campaignId}`);
          mutateSummary();
        }}
        openRecipients={() => setRecipientsModalOpen(true)}
      />

      {/* B. Select Sender Modal */}
      <SenderSelectionDialog
        isOpen={senderModalOpen}
        onClose={() => setSenderModalOpen(false)}
        senders={senders || []}
        selectedEmail={summary?.sender_email || ""}
        onSelect={async (senderId) => {
          await handleSelectSender(senderId);
          setSenderModalOpen(false);
        }}
      />

      {/* C. Select Recipients Modal */}
      <RecipientsDialog
        isOpen={recipientsModalOpen}
        onClose={() => setRecipientsModalOpen(false)}
        campaignId={campaignId as string}
        mutateSummary={mutateSummary}
        mutateValSummary={mutateValSummary}
      />

      {/* D. Preview Modal */}
      <PreviewDialog
        isOpen={previewModalOpen}
        onClose={() => setPreviewModalOpen(false)}
        campaignId={campaignId as string}
      />

      {/* E. Attachment Modal */}
      <AttachmentDialog
        isOpen={attachmentModalOpen}
        onClose={() => setAttachmentModalOpen(false)}
        campaignId={campaignId as string}
        mutateSummary={mutateSummary}
      />

      {/* F. Template Modal */}
      <TemplateDialog
        isOpen={templateModalOpen}
        onClose={() => setTemplateModalOpen(false)}
        onSelect={(tplSub, tplBody) => {
          setSubject(tplSub);
          setBody(tplBody);
          setTemplateModalOpen(false);
        }}
      />
    </div>
  );
}

// ----------------------------------------------------
// Dialog Components Helpers
// ----------------------------------------------------

// 3. Select Recipients Dialog
function RecipientsDialog({
  isOpen,
  onClose,
  campaignId,
  mutateSummary,
  mutateValSummary
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  mutateSummary: () => void;
  mutateValSummary: () => void;
}) {
  const [rawPaste, setRawPaste] = useState("");
  const [sheetUrl, setSheetUrl] = useState("");
  const [tabName, setTabName] = useState("");
  const [sheetTabs, setSheetTabs] = useState<Array<{ title: string; gid?: string | null }>>([]);
  const [tabsLoading, setTabsLoading] = useState(false);
  const [tabsError, setTabsError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);

  useEffect(() => {
    const trimmedUrl = sheetUrl.trim();
    if (!trimmedUrl) {
      setSheetTabs([]);
      setTabsError("");
      setTabsLoading(false);
      return;
    }

    const timeoutId = window.setTimeout(async () => {
      setTabsLoading(true);
      setTabsError("");
      try {
        const res = await fetch(`${API_URL}/api/google-sheets/public-tabs?url=${encodeURIComponent(trimmedUrl)}`);
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || "Could not load tabs");
        }
        const data = await res.json();
        const tabs = Array.isArray(data.tabs) ? data.tabs : [];
        setSheetTabs(tabs);
        if (tabs.length) {
          setTabName(tabs[0].title);
        }
      } catch (err: any) {
        setSheetTabs([]);
        setTabsError(err.message || "Could not load tabs. The sheet may need to be public.");
      } finally {
        setTabsLoading(false);
      }
    }, 500);

    return () => window.clearTimeout(timeoutId);
  }, [sheetUrl]);

  const handlePasteSubmit = async () => {
    if (!rawPaste.trim()) return;
    console.log("[paste] raw text:", rawPaste.slice(0, 200));
    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/api/campaigns/${campaignId}/recipients/paste`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw: rawPaste }),
      });
      const data = await res.json();
      console.log("[paste] response:", data);
      if (!res.ok) throw new Error("Import failed");
      await mutateSummary();
      await mutateValSummary();
      console.log("[paste] valSummary refreshed");
      onClose();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCSVSubmit = async () => {
    if (!csvFile) return;
    console.log("[csv] file:", csvFile.name, csvFile.size, "bytes");
    setIsSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("file", csvFile);
      formData.append("mapping_json", JSON.stringify({}));
      
      const res = await fetch(`${API_URL}/api/campaigns/${campaignId}/recipients/csv`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      console.log("[csv] response:", data);
      if (!res.ok) throw new Error("CSV Upload failed");
      await mutateSummary();
      await mutateValSummary();
      console.log("[csv] valSummary refreshed");
      onClose();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSheetSubmit = async () => {
    if (!sheetUrl.trim()) return;
    console.log("[sheet] url:", sheetUrl, "tab:", tabName);
    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/api/campaigns/${campaignId}/recipients/google-sheet`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: sheetUrl,
          tab_name: tabName,
          header_row: 1,
          mapping: {}
        }),
      });
      const data = await res.json();
      console.log("[sheet] response:", data);
      if (!res.ok) throw new Error("Google sheet fetch failed");
      await mutateSummary();
      await mutateValSummary();
      onClose();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Select recipients</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="paste" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="paste" className="gap-1">
              <ClipboardList className="w-3.5 h-3.5" />
              <span>Copy / paste</span>
            </TabsTrigger>
            <TabsTrigger value="csv" className="gap-1">
              <Upload className="w-3.5 h-3.5" />
              <span>Import CSV</span>
            </TabsTrigger>
            <TabsTrigger value="sheet" className="gap-1">
              <FileSpreadsheet className="w-3.5 h-3.5" />
              <span>Google Sheets</span>
            </TabsTrigger>
          </TabsList>
          
          {/* A. Copy Paste */}
          <TabsContent value="paste" className="py-4 space-y-4">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Paste raw email addresses or CSV format</label>
              <Textarea
                placeholder="e.g. John Doe, john@company.com, Company Name&#10;Jane Smith, jane@company.com"
                value={rawPaste}
                onChange={(e) => setRawPaste(e.target.value)}
                className="min-h-[160px] text-xs font-mono"
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={handlePasteSubmit} disabled={isSubmitting || !rawPaste.trim()}>
                {isSubmitting ? "Importing..." : "Use contacts"}
              </Button>
            </DialogFooter>
          </TabsContent>

          {/* B. Import CSV */}
          <TabsContent value="csv" className="py-4 space-y-4">
            <div className="border-2 border-dashed border-slate-200 hover:border-blue-400 rounded-lg p-8 text-center cursor-pointer transition-colors relative">
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
              />
              <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <div className="text-sm font-semibold text-slate-700">
                {csvFile ? csvFile.name : "Click to select CSV File"}
              </div>
              <p className="text-xs text-slate-400 mt-1">Accepts CSV files with headers Email, First Name, Company Name</p>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={handleCSVSubmit} disabled={isSubmitting || !csvFile}>
                {isSubmitting ? "Uploading..." : "Import CSV"}
              </Button>
            </DialogFooter>
          </TabsContent>

          {/* C. Google Sheets */}
          <TabsContent value="sheet" className="py-4 space-y-4">
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Google Sheet Shareable link</label>
                <Input
                  placeholder="https://docs.google.com/spreadsheets/d/.../edit?usp=sharing"
                  value={sheetUrl}
                  onChange={(e) => setSheetUrl(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Sheet tab</label>
                {sheetTabs.length > 0 ? (
                  <select
                    value={tabName}
                    onChange={(e) => setTabName(e.target.value)}
                    className="w-full h-10 rounded-md border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-1 focus:ring-blue-500/20"
                  >
                    {sheetTabs.map((tab) => (
                      <option key={`${tab.title}-${tab.gid || ""}`} value={tab.title}>
                        {tab.title}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    placeholder={tabsLoading ? "Loading tabs..." : "Default first tab"}
                    value={tabName}
                    onChange={(e) => setTabName(e.target.value)}
                    disabled={tabsLoading}
                  />
                )}
                {tabsError && (
                  <p className="text-[11px] text-amber-600 leading-relaxed">
                    {tabsError}
                  </p>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={handleSheetSubmit} disabled={isSubmitting || !sheetUrl.trim()}>
                {isSubmitting ? "Fetching..." : "Use sheet data"}
              </Button>
            </DialogFooter>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

// 6. Template Dialog
function TemplateDialog({
  isOpen,
  onClose,
  onSelect
}: {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (subject: string, body: string) => void;
}) {
  const { data: templates } = useSWR(
    isOpen ? `${API_URL}/api/templates` : null,
    fetcher
  );
  const list = Array.isArray(templates) ? templates : [];

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Select email template</DialogTitle>
        </DialogHeader>
        <div className="py-4 space-y-4">
          {list.length === 0 ? (
            <p className="text-center text-sm text-slate-400 py-8">No templates yet. Create one from the Templates page.</p>
          ) : (
            list.map((t: any) => (
              <div
                key={t.id}
                className="border border-slate-200 hover:border-blue-400 rounded-lg p-4 cursor-pointer hover:bg-blue-50/10 transition-all space-y-2"
                onClick={() => onSelect(t.subject, t.body)}
              >
                <h3 className="font-bold text-slate-800 text-sm">{t.title}</h3>
                <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                  {t.body}
                </p>
              </div>
            ))
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
