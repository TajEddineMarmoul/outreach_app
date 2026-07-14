import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Paperclip } from "lucide-react";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function AttachmentDialog({
  isOpen,
  onClose,
  campaignId,
  mutateSummary,
  currentAttachment,
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  mutateSummary: () => void | Promise<unknown>;
  currentAttachment?: {
    filename?: string;
    content_type?: string;
    size_bytes?: number;
  } | null;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const { authFetch } = useApiClient();

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/attachment`, {
        method: "POST",
        body: formData,
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(result.detail || "Upload failed");
      await mutateSummary();
      setFile(null);
      onClose();
    } catch (error) {
      alert(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add campaign attachment</DialogTitle>
        </DialogHeader>
        <div className="py-4 space-y-4">
          {currentAttachment?.filename && (
            <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
              <Paperclip className="w-4 h-4 text-blue-600 shrink-0" />
              <div className="min-w-0">
                <div className="text-xs font-semibold text-slate-500">Current attachment</div>
                <div className="text-sm font-medium text-slate-800 truncate">{currentAttachment.filename}</div>
                {currentAttachment.size_bytes !== undefined && (
                  <div className="text-xs text-slate-400">
                    {(currentAttachment.size_bytes / 1024 / 1024).toFixed(2)} MB
                  </div>
                )}
              </div>
            </div>
          )}
          <div className="border-2 border-dashed border-slate-200 hover:border-blue-400 rounded-lg p-8 text-center cursor-pointer relative">
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.doc,.docx"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
            />
            <Paperclip className="w-8 h-8 text-slate-400 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-700">
              {file ? file.name : "Click to select a file"}
            </div>
            <p className="text-xs text-slate-400 mt-1">PDF, image, text, or Word document up to 10 MB</p>
            {file && <p className="text-xs text-slate-500 mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={uploading}>Cancel</Button>
          <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={handleUpload} disabled={uploading || !file}>
            {uploading ? "Uploading..." : currentAttachment?.filename ? "Replace file" : "Attach file"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
