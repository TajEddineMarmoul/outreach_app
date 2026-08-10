"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, Check, LockKeyhole, Send } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

export default function SignInPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch("/api/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        setError(payload.detail || "Sign-in failed. Try again.");
        return;
      }
      const next = searchParams.get("next");
      router.replace(next?.startsWith("/") && !next.startsWith("//") ? next : "/campaigns");
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen w-full bg-[#eef3f8] p-4 sm:p-8">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-6xl overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-[0_30px_90px_-45px_rgba(15,23,42,0.45)] sm:min-h-[calc(100vh-4rem)] lg:grid-cols-[1.15fr_0.85fr]">
        <section className="relative hidden overflow-hidden bg-[#102a43] p-12 text-white lg:flex lg:flex-col lg:justify-between">
          <div className="absolute inset-x-0 top-1/2 h-px bg-blue-300/20" />
          <div className="absolute -right-24 top-24 h-64 w-64 rounded-full border border-blue-300/15" />
          <div className="absolute -right-10 top-38 h-36 w-36 rounded-full border border-blue-300/20" />

          <div className="relative flex items-center gap-3 text-sm font-semibold tracking-wide text-blue-100">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 shadow-lg shadow-blue-950/30">
              <Send className="h-5 w-5" />
            </span>
            OUTREACH / PRIVATE CONSOLE
          </div>

          <div className="relative max-w-xl">
            <p className="mb-5 font-mono text-xs uppercase tracking-[0.28em] text-blue-300">Delivery lane is ready</p>
            <h1 className="text-5xl font-semibold leading-[1.04] tracking-[-0.045em]">
              Messages move only when every field has a value.
            </h1>
            <div className="mt-9 flex flex-wrap gap-2 font-mono text-xs">
              {["{{First Name}}", "{{Company Name}}", "{{keyword_3}}"].map((variable) => (
                <span key={variable} className="rounded-full border border-blue-200/20 bg-white/8 px-3 py-2 text-blue-100">
                  {variable}
                </span>
              ))}
            </div>
          </div>

          <div className="relative grid grid-cols-2 gap-4 border-t border-white/10 pt-6 text-sm text-blue-100">
            <span className="flex items-center gap-2"><Check className="h-4 w-4 text-cyan-300" />Missing rows are skipped</span>
            <span className="flex items-center gap-2"><Check className="h-4 w-4 text-cyan-300" />Sending runs every minute</span>
          </div>
        </section>

        <section className="flex items-center justify-center p-7 sm:p-12">
          <div className="w-full max-w-sm">
            <div className="mb-10 flex items-center gap-3 lg:hidden">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white"><Send className="h-5 w-5" /></span>
              <span className="font-semibold text-slate-900">Outreach</span>
            </div>
            <div className="mb-8 flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-700">
              <LockKeyhole className="h-5 w-5" />
            </div>
            <p className="mb-2 font-mono text-xs uppercase tracking-[0.22em] text-blue-700">Owner access</p>
            <h2 className="text-3xl font-semibold tracking-[-0.035em] text-slate-950">Unlock your workspace</h2>
            <p className="mt-3 text-sm leading-6 text-slate-500">Enter the private deployment password. Your session stays on this device for 30 days.</p>

            <form onSubmit={signIn} className="mt-8 space-y-5">
              <div>
                <label htmlFor="password" className="mb-2 block text-sm font-medium text-slate-700">Workspace password</label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  autoFocus
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-slate-950 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                  placeholder="Enter password"
                />
              </div>
              {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">{error}</p>}
              <button
                type="submit"
                disabled={submitting}
                className="group flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 font-semibold text-white shadow-lg shadow-blue-600/20 transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-wait disabled:opacity-60"
              >
                {submitting ? "Unlocking…" : "Open campaign manager"}
                {!submitting && <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />}
              </button>
            </form>
          </div>
        </section>
      </div>
    </main>
  );
}
