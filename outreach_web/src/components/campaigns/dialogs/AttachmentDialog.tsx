import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { FileText, Loader2, Paperclip, Trash2, X } from "lucide-react";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface CampaignAttachmentSummary {
  id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
}

function formatBytes(size: number): string {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / 1024 / 1024).toFixed(2)} MB`;
}

export default function AttachmentDialog({
  isOpen,
  onClose,
  campaignId,
  mutateSummary,
  attachments,
  deletingAttachmentId,
  onRemoveAttachment,
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  mutateSummary: () => void | Promise<unknown>;
  attachments: CampaignAttachmentSummary[];
  deletingAttachmentId: number | null;
  onRemoveAttachment: (attachmentId: number) => Promise<void>;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const { authFetch } = useApiClient();

  const handleClose = () => {
    if (uploading) return;
    setFiles([]);
    onClose();
  };

  const handleSelectedFiles = (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;
    setFiles((current) => {
      const next = [...current];
      for (const selected of Array.from(selectedFiles)) {
        const duplicate = next.some(
          (file) => file.name === selected.name && file.size === selected.size && file.lastModified === selected.lastModified
        );
        if (!duplicate) next.push(selected);
      }
      return next;
    });
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    try {
      const formData = new FormData();
      files.forEach((file) => formData.append("files", file));
      const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/attachments`, {
        method: "POST",
        body: formData,
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(result.detail || "Upload failed");
      await mutateSummary();
      setFiles([]);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
    >
      <DialogContent className="sm:max-w-lg max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Campaign attachments</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-3 space-y-4">
          {attachments.length > 0 && (
            <div className="border border-slate-200 rounded-md overflow-hidden">
              {attachments.map((attachment) => (
                <div
                  key={attachment.id}
                  className="flex items-center gap-3 px-3 py-2.5 border-b border-slate-100 last:border-b-0"
                >
                  <FileText className="w-4 h-4 text-blue-600 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-slate-800 truncate">{attachment.filename}</div>
                    <div className="text-xs text-slate-400">{formatBytes(attachment.size_bytes)}</div>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-slate-400 hover:text-red-600"
                    onClick={() => onRemoveAttachment(attachment.id)}
                    disabled={uploading || deletingAttachmentId === attachment.id}
                    title={`Remove ${attachment.filename}`}
                  >
                    {deletingAttachmentId === attachment.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              ))}
            </div>
          )}

          <div className="border-2 border-dashed border-slate-200 hover:border-blue-400 rounded-md p-6 text-center cursor-pointer relative">
            <input
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.doc,.docx"
              onChange={(event) => {
                handleSelectedFiles(event.target.files);
                event.target.value = "";
              }}
              className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
            />
            <Paperclip className="w-7 h-7 text-slate-400 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-700">Select files</div>
            <p className="text-xs text-slate-400 mt-1">10 MB per file, 20 MB total</p>
          </div>

          {files.length > 0 && (
            <div className="border border-slate-200 rounded-md overflow-hidden">
              {files.map((file, index) => (
                <div
                  key={`${file.name}-${file.size}-${file.lastModified}`}
                  className="flex items-center gap-3 px-3 py-2 border-b border-slate-100 last:border-b-0"
                >
                  <Paperclip className="w-4 h-4 text-slate-400 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-slate-700 truncate">{file.name}</div>
                    <div className="text-xs text-slate-400">{formatBytes(file.size)}</div>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setFiles((current) => current.filter((_, fileIndex) => fileIndex !== index))}
                    disabled={uploading}
                    title={`Remove ${file.name} from upload`}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={uploading}>Close</Button>
          <Button
            className="bg-blue-600 hover:bg-blue-700 text-white"
            onClick={handleUpload}
            disabled={uploading || files.length === 0}
          >
            {uploading
              ? "Uploading..."
              : files.length === 0
                ? "Attach files"
                : `Attach ${files.length} file${files.length === 1 ? "" : "s"}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
