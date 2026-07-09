"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function OAuthCallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { authFetch } = useApiClient();
  const [status, setStatus] = useState("Exchanging authorization code...");

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");

    if (error) {
      setStatus(`Authorization failed: ${error}`);
      setTimeout(() => router.push("/senders"), 2000);
      return;
    }

    if (!code) {
      setStatus("No authorization code received");
      setTimeout(() => router.push("/senders"), 2000);
      return;
    }

    authFetch(`${API_URL}/api/oauth/callback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, state }),
    })
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json()).detail || "Failed");
        const data = await res.json();
        setStatus(`Authorized as ${data.email}! Redirecting...`);
        setTimeout(() => router.push("/senders?oauth=success"), 1500);
      })
      .catch((err) => {
        setStatus(`Error: ${err.message}`);
        setTimeout(() => router.push("/senders"), 2000);
      });
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50/30">
      <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm text-center max-w-md">
        {status.includes("Error") ? (
          <div className="w-12 h-12 bg-red-50 border border-red-200 rounded-full flex items-center justify-center mx-auto mb-4 text-red-500 text-xl">✕</div>
        ) : (
          <div className="w-12 h-12 bg-blue-50 border border-blue-200 rounded-full flex items-center justify-center mx-auto mb-4">
            <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
        <p className="text-sm text-slate-600">{status}</p>
      </div>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-slate-50/30">
        <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm text-center max-w-md">
          <div className="w-12 h-12 bg-blue-50 border border-blue-200 rounded-full flex items-center justify-center mx-auto mb-4">
            <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          </div>
          <p className="text-sm text-slate-600">Loading...</p>
        </div>
      </div>
    }>
      <OAuthCallbackInner />
    </Suspense>
  );
}
