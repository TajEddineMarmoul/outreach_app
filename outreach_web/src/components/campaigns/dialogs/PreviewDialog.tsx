import { useState, useEffect } from "react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ChevronLeft, ChevronRight, Paperclip } from "lucide-react";
import { cn } from "@/lib/utils";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function PreviewDialog({
  isOpen,
  onClose,
  campaignId
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
}) {
  const { data: previews, mutate: mutatePreviews } = useSWR(
    isOpen ? `${API_URL}/api/campaigns/${campaignId}/preview` : null
  );
  const { authFetch } = useApiClient();
  
  const [testEmail, setTestEmail] = useState("");
  const [testSending, setTestSending] = useState(false);
  const [previewIndex, setPreviewIndex] = useState(0);
  const previewRows = Array.isArray(previews) ? previews : [];
  const currentPreview = previewRows[previewIndex] || null;
  const hasPreviews = previewRows.length > 0 && previewRows[0]?.subject !== null && previewRows[0]?.subject !== undefined;

  const [testResult, setTestResult] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    setPreviewIndex(0);
    setTestResult(null);
  }, [isOpen, previewRows.length]);

  const handleGenerate = async () => {
    await authFetch(`${API_URL}/api/campaigns/${campaignId}/preview/generate`, { method: "POST" });
    mutatePreviews();
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
    } catch (err: any) {
      setTestResult({ type: "error", message: err.message });
    } finally {
      setTestSending(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between gap-4">
            <DialogTitle>Email campaign preview</DialogTitle>
            {previewRows.length > 0 && (
              <div className="flex items-center gap-2">
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
                  {previewIndex + 1} / {previewRows.length}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setPreviewIndex((idx) => Math.min(previewRows.length - 1, idx + 1))}
                  disabled={previewIndex >= previewRows.length - 1}
                  title="Next preview"
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            )}
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-4 py-4 min-h-[300px]">
          {!hasPreviews ? (
            <div className="p-12 text-center text-slate-500 space-y-3">
              <p>No preview rows generated. Previews must be generated before campaign sending.</p>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={handleGenerate}>
                Generate previews
              </Button>
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
            {currentPreview.attachment_name && currentPreview.attachment_name !== "none" && (
              <div className="px-4 py-3 bg-slate-50 flex items-center gap-2 text-xs font-semibold text-slate-600">
                <Paperclip className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                <span>{currentPreview.attachment_name}</span>
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
            <Button variant="outline" onClick={onClose} className="self-end sm:self-auto">Close</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
