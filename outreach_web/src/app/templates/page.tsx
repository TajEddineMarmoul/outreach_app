"use client";

import { useState } from "react";
import { Plus, FileText, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import useSWR from "swr";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

interface Template {
  id: number;
  title: string;
  subject: string;
  body: string;
}

export default function TemplatesPage() {
  const { data: templates, mutate } = useSWR<Template[]>(`${API_URL}/api/templates`);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const { authFetch } = useApiClient();

  const handleCreate = async () => {
    if (!title.trim() || !subject.trim() || !body.trim()) return;
    await authFetch(`${API_URL}/api/templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.trim(), subject: subject.trim(), body }),
    });
    mutate();
    setTitle("");
    setSubject("");
    setBody("");
    setOpen(false);
  };

  const handleDelete = async (id: number) => {
    await authFetch(`${API_URL}/api/templates/${id}`, { method: "DELETE" });
    mutate();
  };

  const list = templates ?? [];

  return (
    <div className="p-8 space-y-6 max-w-6xl mx-auto w-full">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Templates</h1>
          <p className="text-slate-500 text-sm mt-1">Reusable email subject & body templates</p>
        </div>
        <Button onClick={() => setOpen(true)} className="bg-blue-600 hover:bg-blue-700 text-white gap-2">
          <Plus className="w-4 h-4" />
          New template
        </Button>
      </div>

      {list.length === 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-16 text-center space-y-3 shadow-sm">
          <div className="mx-auto w-12 h-12 bg-slate-50 border border-slate-200 rounded-full flex items-center justify-center text-slate-400">
            <FileText className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-slate-900 text-lg">No templates yet</h3>
          <p className="text-slate-500 text-sm max-w-sm mx-auto">
            Create reusable templates to quickly fill subject and body in any campaign.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {list.map((tpl) => (
          <Card key={tpl.id} className="border-slate-200 shadow-sm">
            <CardHeader className="border-b border-slate-100 flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-600" />
                <span>{tpl.title}</span>
              </CardTitle>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-slate-500 hover:text-red-600"
                onClick={() => handleDelete(tpl.id)}
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </CardHeader>
            <CardContent className="pt-4 space-y-2 text-xs">
              <div className="text-slate-500 font-semibold">Subject: <span className="font-normal text-slate-800">{tpl.subject}</span></div>
              <div className="whitespace-pre-wrap text-slate-600 font-sans leading-relaxed pt-2 h-40 overflow-y-auto border border-slate-50 p-2 rounded bg-slate-50/30">
                {tpl.body}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create template</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="text-xs font-medium text-slate-600 mb-1 block">Title</label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Job Application outreach" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 mb-1 block">Subject</label>
              <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Junior Technical Profile - {{ Company_Name }}" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 mb-1 block">Body</label>
              <Textarea value={body} onChange={(e) => setBody(e.target.value)} className="min-h-[200px] text-xs" placeholder="Write your template body..." />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} className="bg-blue-600 hover:bg-blue-700 text-white">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
