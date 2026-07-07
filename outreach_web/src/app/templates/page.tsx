"use client";

import { useState } from "react";
import { Plus, Mail, FileText, Trash2, Edit } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function TemplatesPage() {
  const [templates, setTemplates] = useState([
    {
      id: 1,
      title: "Job Application outreach",
      subject: "Junior Technical Profile - {{ Company_Name }}",
      body: "Hi {{ First_Name }},\n\nI found your LinkedIn profile while looking at {{ Company_Name }}, and I noticed that the company focuses on job keywords.\n\nMy name is Your Name. I am a final-year AI & Computer Science engineering student.\n\nI'm looking for a junior/intern technical role starting around October 2026, and I want to contribute to your engineering team.\n\nCould we jump on a brief 10-minute call this week? I have attached my resume for your review.\n\nBest regards,\nYour Name",
    },
    {
      id: 2,
      title: "Sales / Product Pitch",
      subject: "Quick question about {{ Company_Name }}'s engineering stack",
      body: "Hi {{ First_Name }},\n\nHope you are doing well.\n\nI was looking at {{ Company_Name }} and saw that you are scale-testing your tech stack. We help companies automate their API workflows with zero downtime.\n\nWould you be open to a quick call next Tuesday at 2 PM to see if we can help?\n\nBest,\nYour Name",
    },
  ]);

  return (
    <div className="p-8 space-y-6 max-w-6xl mx-auto w-full">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Templates</h1>
        <p className="text-slate-500 text-sm mt-1">Manage reusable email subject & body templates</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {templates.map((tpl) => (
          <Card key={tpl.id} className="border-slate-200 hover:border-blue-400 transition-colors shadow-sm">
            <CardHeader className="border-b border-slate-100 flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-600" />
                <span>{tpl.title}</span>
              </CardTitle>
              <div className="flex gap-1">
                <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500 hover:text-blue-600">
                  <Edit className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-slate-500 hover:text-red-600"
                  onClick={() => setTemplates(templates.filter((t) => t.id !== tpl.id))}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
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
    </div>
  );
}
