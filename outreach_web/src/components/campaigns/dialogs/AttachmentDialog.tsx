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
  mutateSummary
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  mutateSummary: () => void;
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
      if (!res.ok) throw new Error("Upload failed");
      mutateSummary();
      onClose();
    } catch (err: any) {
      alert(err.message);
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
          <div className="border-2 border-dashed border-slate-200 hover:border-blue-400 rounded-lg p-8 text-center cursor-pointer relative">
            <input
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="absolute inset-0 opacity-0 w-full h-full cursor-pointer"
            />
            <Paperclip className="w-8 h-8 text-slate-400 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-700">
              {file ? file.name : "Click to select a file"}
            </div>
            <p className="text-xs text-slate-400 mt-1">Supported formats: PDF, Images, Document up to 10MB</p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={uploading}>Cancel</Button>
          <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={handleUpload} disabled={uploading || !file}>
            {uploading ? "Uploading..." : "Attach file"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
