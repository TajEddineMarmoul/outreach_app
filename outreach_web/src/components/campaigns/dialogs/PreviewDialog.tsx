import { useState } from "react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ChevronLeft, ChevronRight, Loader2, Paperclip, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useApiClient } from "@/lib/api";
import type { CampaignAttachmentSummary } from "@/components/campaigns/dialogs/AttachmentDialog";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

interface PreviewEntry {
  id: number;
  recipient_email: string;
  subject: string;
  body: string;
  attachment_name: string;
  attachments: CampaignAttachmentSummary[];
}

interface PreviewResponse {
  items: PreviewEntry[];
  total: number;
  offset: number;
  limit: number;
}

export default function PreviewDialog({
  isOpen,
  onClose,
  campaignId
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
}) {
  const [previewIndex, setPreviewIndex] = useState(0);
  const { data: previews, isLoading } = useSWR<PreviewResponse>(
    isOpen ? `${API_URL}/api/campaigns/${campaignId}/preview?offset=${previewIndex}&limit=1` : null,
    { keepPreviousData: true }
  );
  const { authFetch } = useApiClient();
  
  const [testEmail, setTestEmail] = useState("");
  const [testSending, setTestSending] = useState(false);
  const currentPreview = previews?.items?.[0] || null;
  const previewTotal = previews?.total || 0;

  const [testResult, setTestResult] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const handleClose = () => {
    setPreviewIndex(0);
    setTestResult(null);
    onClose();
  };

  const handleSendTest = async () => {
    if (!testEmail.trim()) return;
    setTestSending(true);
    setTestResult(null);
    try {
      const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/test-send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recipient_email: testEmail,
          preview_contact_id: currentPreview?.id,
        }),
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => null);
        throw new Error(errorData?.detail || "Test send failed");
      }
      setTestResult({ type: "success", message: "Test email sent successfully!" });
    } catch (error) {
      setTestResult({
        type: "error",
        message: error instanceof Error ? error.message : "Test send failed",
      });
    } finally {
      setTestSending(false);
    }
  };

  return (
    <Dialog
      open={isOpen}
      disablePointerDismissal
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
    >
      <DialogContent showCloseButton={false} className="sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between gap-4">
            <DialogTitle>Email campaign preview</DialogTitle>
            <div className="flex items-center gap-2">
              {previewTotal > 0 && (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setPreviewIndex((idx) => Math.max(0, idx - 1))}
                    disabled={previewIndex === 0}
                    title="Previous preview"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <span className="text-xs font-semibold text-slate-500 min-w-16 text-center">
                    {previewIndex + 1} / {previewTotal}
                  </span>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setPreviewIndex((idx) => Math.min(previewTotal - 1, idx + 1))}
                    disabled={previewIndex >= previewTotal - 1}
                    title="Next preview"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </>
              )}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={handleClose}
                title="Close preview"
              >
                <X className="w-4 h-4" />
                <span className="sr-only">Close preview</span>
              </Button>
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-4 py-4 min-h-[300px]">
          {isLoading ? (
            <div className="p-12 flex items-center justify-center text-sm text-slate-500">
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              Loading preview...
            </div>
          ) : !currentPreview ? (
            <div className="p-12 text-center text-slate-500">
              <p>Add at least one recipient to preview this campaign.</p>
            </div>
          ) : (
            <div className="border border-slate-200 rounded-lg bg-white overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 text-xs flex items-center justify-between gap-3">
                <span className="text-slate-500 truncate">
                  To: <strong className="text-slate-800">{currentPreview.recipient_email}</strong>
                </span>
                <span className="text-slate-400 shrink-0">Row {previewIndex + 1}</span>
              </div>
              <div className="px-4 py-3 border-b border-slate-100 text-sm font-semibold text-slate-800">
                Subject: {currentPreview.subject || "(empty subject)"}
              </div>
            <div className="px-4 py-4 text-slate-700 leading-relaxed font-sans text-sm border-b border-slate-100">
              {currentPreview.body ? (
                /<[a-z][\s\S]*>/i.test(currentPreview.body) ? (
                  <div dangerouslySetInnerHTML={{ __html: currentPreview.body }} />
                ) : (
                  <div className="whitespace-pre-wrap">{currentPreview.body}</div>
                )
              ) : (
                "(empty body)"
              )}
            </div>
            {currentPreview.attachments?.length > 0 && (
              <div className="px-4 py-3 bg-slate-50 space-y-2">
                {currentPreview.attachments.map((attachment) => (
                  <div key={attachment.id} className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                    <Paperclip className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                    <span className="truncate">{attachment.filename}</span>
                  </div>
                ))}
              </div>
            )}
            </div>
          )}
        </div>

        <div className="border-t border-slate-200 pt-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex flex-col w-full sm:max-w-sm gap-2">
              <div className="flex items-center gap-2">
                <Input
                  type="email"
                  placeholder="recipient@domain.com"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  className="text-xs"
                />
                <Button
                  className="bg-slate-800 hover:bg-slate-900 text-white text-xs shrink-0"
                  onClick={handleSendTest}
                  disabled={testSending || !testEmail.trim() || !currentPreview}
                >
                  {testSending ? "Sending..." : "Send test"}
                </Button>
              </div>
              {testResult && (
                <div className={cn("text-[11px] font-medium px-1", testResult.type === "success" ? "text-emerald-600" : "text-red-500")}>
                  {testResult.message}
                </div>
              )}
            </div>
            <Button variant="outline" onClick={handleClose} className="self-end sm:self-auto">Close</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
