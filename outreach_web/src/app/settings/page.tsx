"use client";

import { useState, useEffect, useRef } from "react";
import useSWR, { mutate } from "swr";
import { Settings, ShieldAlert, Key, CheckCircle, AlertTriangle, Loader2, Upload, HelpCircle, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from "@/components/ui/dialog";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => {
  if (!r.ok) throw new Error("API call failed");
  return r.json();
});

export default function SettingsPage() {
  const { data: settings, isLoading: settingsLoading } = useSWR(`${API_URL}/api/settings`, fetcher);
  const { data: oauth, isLoading: oauthLoading, mutate: mutateOauth } = useSWR(`${API_URL}/api/oauth/status`, fetcher);

  // Form states
  const [timezone, setTimezone] = useState("UTC");
  const [maxDailyCap, setMaxDailyCap] = useState(10);
  const [bounceRate, setBounceRate] = useState(0.1);
  const [maxErrors, setMaxErrors] = useState(5);
  const [savingSettings, setSavingSettings] = useState(false);

  // Credentials input states
  const [uploadMode, setUploadMode] = useState<"paste" | "form">("paste");
  const [credentialsJson, setCredentialsJson] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [savingCreds, setSavingCreds] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (settings) {
      setTimezone(settings.timezone || "UTC");
      setMaxDailyCap(settings.max_daily_cap || 10);
      setBounceRate(settings.bounce_rate_pause_threshold || 0.1);
      setMaxErrors(settings.max_consecutive_errors || 5);
    }
  }, [settings]);

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSettings(true);
    try {
      const res = await fetch(`${API_URL}/api/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          timezone,
          max_daily_cap: maxDailyCap,
          bounce_rate_pause_threshold: bounceRate,
          max_consecutive_errors: maxErrors,
        }),
      });
      if (!res.ok) throw new Error("Failed to save settings");
      mutate(`${API_URL}/api/settings`);
      alert("Settings saved successfully!");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSavingSettings(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      try {
        // Validate JSON structure
        JSON.parse(content);
        setCredentialsJson(content);
      } catch (err) {
        alert("Invalid JSON file. Please verify its content.");
      }
    };
    reader.readAsText(file);
  };

  const handleSaveCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    let bodyContent = "";

    if (uploadMode === "paste") {
      bodyContent = credentialsJson.trim();
    } else {
      if (!clientId.trim() || !clientSecret.trim()) {
        alert("Please fill in all manual credential fields.");
        return;
      }
      bodyContent = JSON.stringify({
        installed: {
          client_id: clientId.trim(),
          auth_uri: "https://accounts.google.com/o/oauth2/auth",
          token_uri: "https://oauth2.googleapis.com/token",
          auth_provider_x509_cert_url: "https://www.googleapis.com/oauth2/v1/certs",
          client_secret: clientSecret.trim(),
          redirect_uris: ["http://localhost"]
        }
      }, null, 2);
    }

    if (!bodyContent) return;

    setSavingCreds(true);
    try {
      const res = await fetch(`${API_URL}/api/oauth/save-credentials-json`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: bodyContent }),
      });
      if (!res.ok) throw new Error("Invalid credentials JSON structure");
      mutateOauth();
      setCredentialsJson("");
      setClientId("");
      setClientSecret("");
      alert("credentials.json saved successfully!");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSavingCreds(false);
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-4xl mx-auto w-full">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Settings</h1>
        <p className="text-slate-500 text-sm mt-1">Configure global application caps, safety parameters, and API credentials</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Left column: Global Config */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
            <Settings className="w-4 h-4 text-blue-600" />
            <span>Safety Defaults</span>
          </h2>

          {settingsLoading ? (
            <div className="flex items-center gap-2 text-slate-500 text-xs">
              <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
              <span>Loading configurations...</span>
            </div>
          ) : (
            <form onSubmit={handleSaveSettings} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Timezone</label>
                <Input value={timezone} onChange={(e) => setTimezone(e.target.value)} />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Absolute Max Daily Cap</label>
                <Input type="number" value={maxDailyCap} onChange={(e) => setMaxDailyCap(Number(e.target.value))} />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Bounce Rate Pause Threshold (e.g. 0.1 = 10%)</label>
                <Input type="number" step="0.01" value={bounceRate} onChange={(e) => setBounceRate(Number(e.target.value))} />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Max Consecutive Errors</label>
                <Input type="number" value={maxErrors} onChange={(e) => setMaxErrors(Number(e.target.value))} />
              </div>

              <Button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white w-full" disabled={savingSettings}>
                {savingSettings ? "Saving..." : "Save settings"}
              </Button>
            </form>
          )}
        </div>

        {/* Right column: OAuth Credentials */}
        <div className="space-y-6">
          {/* Credentials Status */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-slate-900 flex items-center justify-between border-b border-slate-100 pb-3">
              <span className="flex items-center gap-2">
                <Key className="w-4 h-4 text-blue-600" />
                <span>Google Cloud Platform Status</span>
              </span>
              
              <Dialog>
                <DialogTrigger className="text-xs text-blue-600 hover:text-blue-800 font-semibold cursor-pointer flex items-center gap-1">
                  <HelpCircle className="w-3.5 h-3.5" />
                  <span>Troubleshoot</span>
                </DialogTrigger>
                <DialogContent className="max-w-md p-6 bg-white rounded-xl shadow-lg border border-slate-200">
                  <DialogHeader className="space-y-1">
                    <DialogTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
                      <HelpCircle className="w-5 h-5 text-blue-600" />
                      <span>GCP Troubleshooter</span>
                    </DialogTitle>
                    <DialogDescription className="text-xs text-slate-500">
                      Follow these diagnostic checks to debug your Google Cloud Platform (GCP) integration.
                    </DialogDescription>
                  </DialogHeader>

                  <div className="space-y-4 my-4">
                    {/* Step 1 */}
                    <div className="space-y-1 bg-slate-50/50 p-3 rounded-lg border border-slate-100 text-left">
                      <div className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                        <span className="w-4 h-4 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-[10px]">1</span>
                        <span>Enable Google Cloud APIs</span>
                      </div>
                      <p className="text-[11px] text-slate-500 pl-5 leading-relaxed">
                        Gmail API must be enabled in your Google Cloud Console before sender OAuth can send messages.
                      </p>
                      <div className="flex gap-2 pl-5 pt-1.5">
                        <a
                          href="https://console.cloud.google.com/apis/library/gmail.googleapis.com"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] text-blue-600 hover:underline flex items-center gap-0.5 font-semibold"
                        >
                          Enable Gmail API <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      </div>
                    </div>

                    {/* Step 2 */}
                    <div className="space-y-1 bg-slate-50/50 p-3 rounded-lg border border-slate-100 text-left">
                      <div className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                        <span className="w-4 h-4 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-[10px]">2</span>
                        <span>OAuth Application Type</span>
                      </div>
                      <p className="text-[11px] text-slate-500 pl-5 leading-relaxed">
                        When creating credentials, you must select <strong>Desktop Application</strong>. Service Accounts or Web App Client IDs will fail.
                      </p>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </h2>

            {oauthLoading ? (
              <div className="flex items-center gap-2 text-slate-500 text-xs">
                <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                <span>Loading GCP status...</span>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Google OAuth Client Row */}
                <div className="flex items-center justify-between text-xs border-b border-slate-50 pb-3">
                  <span className="text-slate-500 font-medium">OAuth Desktop Client</span>
                  {oauth?.credentials_json_present ? (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-50 text-green-700 border border-green-200 inline-flex items-center gap-1">
                      <CheckCircle className="w-3.5 h-3.5" /> Configured
                    </span>
                  ) : (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 inline-flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" /> Not Configured
                    </span>
                  )}
                </div>

                {/* Gmail API Row */}
                <div className="flex items-center justify-between text-xs border-b border-slate-50 pb-3">
                  <span className="text-slate-500 font-medium">Gmail API</span>
                  <div className="flex items-center gap-3">
                    <a
                      href="https://console.cloud.google.com/apis/library/gmail.googleapis.com"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-700 hover:underline font-semibold inline-flex items-center gap-1"
                    >
                      Open in GCP <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>

              </div>
            )}
          </div>

          {/* Paste or Fill Credentials JSON */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <div className="border-b border-slate-100 pb-3 flex items-center justify-between">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-blue-600" />
                <span>Update Credentials</span>
              </h2>

              <div className="flex bg-slate-100 p-0.5 rounded-md text-xs">
                <button
                  onClick={() => setUploadMode("paste")}
                  className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${
                    uploadMode === "paste" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  Upload JSON
                </button>
                <button
                  onClick={() => setUploadMode("form")}
                  className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${
                    uploadMode === "form" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  Fill Form
                </button>
              </div>
            </div>

            <form onSubmit={handleSaveCredentials} className="space-y-4">
              {uploadMode === "paste" ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-700">Paste JSON or Upload File</label>
                    <input
                      type="file"
                      accept=".json"
                      onChange={handleFileUpload}
                      ref={fileInputRef}
                      className="hidden"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="xs"
                      className="text-xs gap-1 border-slate-200 text-slate-600 hover:bg-slate-50"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Upload className="w-3 h-3" />
                      <span>Choose file</span>
                    </Button>
                  </div>
                  <textarea
                    placeholder='{"installed":{"client_id":"...","project_id":"...","client_secret":"..."}}'
                    value={credentialsJson}
                    onChange={(e) => setCredentialsJson(e.target.value)}
                    className="w-full text-xs font-mono min-h-[140px] border border-slate-200 rounded-md p-2 outline-none focus:ring-1 focus:ring-blue-500/20 bg-slate-50/50"
                    disabled={savingCreds}
                  />
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-700">Client ID</label>
                    <Input
                      placeholder="e.g. 12345-abcde.apps.googleusercontent.com"
                      value={clientId}
                      onChange={(e) => setClientId(e.target.value)}
                      disabled={savingCreds}
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-700">Client Secret</label>
                    <Input
                      type="password"
                      placeholder="Enter Google Client Secret"
                      value={clientSecret}
                      onChange={(e) => setClientSecret(e.target.value)}
                      disabled={savingCreds}
                      required
                    />
                  </div>
                </div>
              )}

              <Button
                type="submit"
                className="bg-slate-800 hover:bg-slate-900 text-white w-full shadow-sm"
                disabled={
                  savingCreds ||
                  (uploadMode === "paste" && !credentialsJson.trim()) ||
                  (uploadMode === "form" && (!clientId.trim() || !clientSecret.trim()))
                }
              >
                {savingCreds ? "Uploading..." : "Save credentials"}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
