"use client";

import { FileText } from "lucide-react";

export default function TemplatesPage() {
  return (
    <div className="p-8 space-y-6 max-w-6xl mx-auto w-full">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Templates</h1>
        <p className="text-slate-500 text-sm mt-1">Reusable email subject &amp; body templates</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-16 text-center space-y-3 shadow-sm">
        <div className="mx-auto w-12 h-12 bg-slate-50 border border-slate-200 rounded-full flex items-center justify-center text-slate-400">
          <FileText className="w-5 h-5" />
        </div>
        <h3 className="font-semibold text-slate-900 text-lg">No templates yet</h3>
        <p className="text-slate-500 text-sm max-w-sm mx-auto">
          Write your subject and body directly inside each campaign editor.
        </p>
      </div>
    </div>
  );
}
