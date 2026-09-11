import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  CheckCircle,
  CircleX,
  FileText,
  Loader2,
  Paperclip,
  RotateCcw,
  Trash2,
  X,
} from "lucide-react";
import { API_URL, responseProblem, toBackendProxyUrl } from "@/lib/api";

export interface CampaignAttachmentSummary {
  id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
}

export type AttachmentUploadStatus = "queued" | "uploading" | "uploaded" | "error";

export interface AttachmentUpload {
  id: string;
  file: File;
  filename: string;
  sizeBytes: number;
  progress: number;
  status: AttachmentUploadStatus;
  error?: string;
}

function formatBytes(size: number): string {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / 1024 / 1024).toFixed(2)} MB`;
}

function uploadAttachment({
  campaignId,
  file,
  onProgress,
}: {
  campaignId: string;
  file: File;
  onProgress: (progress: number) => void;
}): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const endpoint = toBackendProxyUrl(
      `${API_URL}/api/campaigns/${campaignId}/attachments`,
    );

    request.open("POST", endpoint);
    request.timeout = 300_000;
    request.setRequestHeader("Accept", "application/json");
    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onload = () => {
      let body: unknown = {};
      try {
        body = JSON.parse(request.responseText);
      } catch {
        // Some failed network responses do not have a JSON body.
      }

      if (request.status >= 200 && request.status < 300) {
        resolve();
        return;
      }
      reject(
        new Error(
          responseProblem(body, "Couldn’t upload this file. Please try again."),
        ),
      );
    };
    request.onerror = () =>
      reject(
        new Error(
          "The upload could not reach the server. Check your connection and retry.",
        ),
      );
    request.ontimeout = () =>
      reject(new Error("The upload took too long. Please try again."));

    const formData = new FormData();
    formData.append("files", file);
    request.send(formData);
  });
}

export function attachmentUploadStatusText(upload: AttachmentUpload): string {
  if (upload.status === "uploaded") return "Uploaded";
  if (upload.status === "error") return "Upload failed";
  if (upload.status === "queued") return "Waiting to upload";
  return upload.progress >= 100 ? "Saving attachment…" : `Uploading ${upload.progress}%`;
}

export default function AttachmentDialog({
  isOpen,
  onClose,
  campaignId,
  mutateSummary,
  attachments,
  deletingAttachmentId,
  onRemoveAttachment,
  onUploadChange,
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  mutateSummary: () => void | Promise<unknown>;
  attachments: CampaignAttachmentSummary[];
  deletingAttachmentId: number | null;
  onRemoveAttachment: (attachmentId: number) => Promise<void>;
  onUploadChange: (uploads: AttachmentUpload[]) => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploads, setUploads] = useState<AttachmentUpload[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    onUploadChange(uploads);
  }, [onUploadChange, uploads]);

  const updateUpload = (uploadId: string, updates: Partial<AttachmentUpload>) => {
    setUploads((current) =>
      current.map((upload) =>
        upload.id === uploadId ? { ...upload, ...updates } : upload,
      ),
    );
  };

  const uploadFiles = async (items: AttachmentUpload[]) => {
    setUploading(true);
    for (const item of items) {
      updateUpload(item.id, { status: "uploading", progress: 0, error: undefined });
      try {
        await uploadAttachment({
          campaignId,
          file: item.file,
          onProgress: (progress) => updateUpload(item.id, { progress }),
        });
        updateUpload(item.id, { status: "uploaded", progress: 100 });
        try {
          await mutateSummary();
        } catch {
          // The file is uploaded even if refreshing the attachment list fails.
        }
      } catch (error) {
        updateUpload(item.id, {
          status: "error",
          error:
            error instanceof Error
              ? error.message
              : "Couldn’t upload this file. Please try again.",
        });
      }
    }
    setUploading(false);
  };

  const handleClose = () => {
    setFiles([]);
    onClose();
  };

  const handleSelectedFiles = (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;
    setFiles((current) => {
      const next = [...current];
      for (const selected of Array.from(selectedFiles)) {
        const duplicate = next.some(
          (file) =>
            file.name === selected.name &&
            file.size === selected.size &&
            file.lastModified === selected.lastModified,
        );
        if (!duplicate) next.push(selected);
      }
      return next;
    });
  };

  const handleUpload = () => {
    if (files.length === 0 || uploading) return;
    const batch = files.map((file, index) => ({
      id: `${Date.now()}-${index}-${file.name}-${file.lastModified}`,
      file,
      filename: file.name,
      sizeBytes: file.size,
      progress: 0,
      status: "queued" as const,
    }));
    setFiles([]);
    setUploads(batch);
    void uploadFiles(batch);
  };

  const retryUpload = (upload: AttachmentUpload) => {
    if (uploading) return;
    void uploadFiles([upload]);
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
          <DialogDescription>
            {uploading
              ? "Your files will keep uploading if you continue editing your email."
              : "Add files to send with every email in this campaign."}
          </DialogDescription>
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
                    <div className="text-sm font-medium text-slate-800 truncate">
                      {attachment.filename}
                    </div>
                    <div className="text-xs text-slate-400">
                      {formatBytes(attachment.size_bytes)}
                    </div>
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

          <div
            className={`border-2 border-dashed border-slate-200 rounded-md p-6 text-center relative ${
              uploading ? "cursor-not-allowed opacity-60" : "hover:border-blue-400 cursor-pointer"
            }`}
          >
            <input
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.doc,.docx"
              disabled={uploading}
              onChange={(event) => {
                handleSelectedFiles(event.target.files);
                event.target.value = "";
              }}
              className="absolute inset-0 opacity-0 w-full h-full cursor-pointer disabled:cursor-not-allowed"
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
                    onClick={() =>
                      setFiles((current) =>
                        current.filter((_, fileIndex) => fileIndex !== index),
                      )
                    }
                    disabled={uploading}
                    title={`Remove ${file.name} from upload`}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          {uploads.length > 0 && (
            <div className="border border-slate-200 rounded-md overflow-hidden" aria-live="polite">
              {uploads.map((upload) => (
                <div
                  key={upload.id}
                  className="flex items-start gap-3 px-3 py-3 border-b border-slate-100 last:border-b-0"
                >
                  {upload.status === "uploaded" ? (
                    <CheckCircle className="mt-0.5 w-4 h-4 text-emerald-600 shrink-0" aria-hidden="true" />
                  ) : upload.status === "error" ? (
                    <CircleX className="mt-0.5 w-4 h-4 text-red-600 shrink-0" aria-hidden="true" />
                  ) : upload.status === "uploading" ? (
                    <Loader2 className="mt-0.5 w-4 h-4 text-blue-600 animate-spin shrink-0" aria-hidden="true" />
                  ) : (
                    <Paperclip className="mt-0.5 w-4 h-4 text-slate-500 shrink-0" aria-hidden="true" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-slate-700 truncate">{upload.filename}</div>
                    <div
                      className={`text-xs mt-0.5 ${
                        upload.status === "error"
                          ? "text-red-700"
                          : upload.status === "uploaded"
                            ? "text-emerald-700"
                            : "text-slate-500"
                      }`}
                      role={upload.status === "error" ? "alert" : undefined}
                    >
                      {attachmentUploadStatusText(upload)}
                      {upload.status === "error" && upload.error ? `: ${upload.error}` : ""}
                    </div>
                    {upload.status === "uploading" && (
                      <progress
                        className="mt-2 block h-1.5 w-full accent-blue-600"
                        value={upload.progress}
                        max="100"
                        aria-label={`${upload.filename} upload progress`}
                      />
                    )}
                  </div>
                  {upload.status === "error" && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-blue-700 hover:text-blue-800"
                      onClick={() => retryUpload(upload)}
                      disabled={uploading}
                    >
                      <RotateCcw className="w-3.5 h-3.5" /> Retry
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            {uploading ? "Continue editing" : "Close"}
          </Button>
          <Button
            className="bg-blue-600 hover:bg-blue-700 text-white"
            onClick={handleUpload}
            disabled={uploading || files.length === 0}
          >
            {uploading
              ? "Uploading…"
              : files.length === 0
                ? "Attach files"
                : `Attach ${files.length} file${files.length === 1 ? "" : "s"}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
