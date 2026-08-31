"use client";

import { X } from "lucide-react";
import { useEffect } from "react";
import type { GuideStep } from "@/lib/onboarding";
import "./onboarding.css";

const content = {
  audience: { title: "Start with your contacts", text: "Paste rows, upload a CSV, or link a Google Sheet. You can review the list before importing." },
  message: { title: "Check before you send", text: "Preview shows an example of your email. Nothing sends until you confirm on Review." },
  review: { title: "Your final checkpoint", text: "Check your audience, message, senders, and schedule. Launching is the step that can start sending." },
};

export default function CampaignGuide({ step, onDismiss, onHideTips }: { step: GuideStep; onDismiss: () => void; onHideTips: () => void }) {
  const item = content[step];
  useEffect(() => {
    const dismiss = (event: KeyboardEvent) => { if (event.key === "Escape") onDismiss(); };
    window.addEventListener("keydown", dismiss);
    return () => window.removeEventListener("keydown", dismiss);
  }, [onDismiss]);
  return (
    <aside className={`campaign-guide is-${step}`} role="dialog" aria-live="polite" aria-label={`Getting started: ${item.title}`}>
      <div className="campaign-guide-top"><span>Quick tip</span><button aria-label="Dismiss tip" onClick={onDismiss}><X size={18} /></button></div>
      <h2>{item.title}</h2>
      <p>{item.text}</p>
      <div className="campaign-guide-actions"><button className="campaign-text-button" onClick={onHideTips}>Hide tips</button><button className="campaign-button is-primary" onClick={onDismiss}>Got it</button></div>
    </aside>
  );
}
