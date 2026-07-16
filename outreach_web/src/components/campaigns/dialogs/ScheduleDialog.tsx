import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}

function toLocalDateTimeInput(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export default function ScheduleDialog({
  isOpen,
  onClose,
  campaignId,
  defaultTab,
  mutateAll,
  summary,
  readOnly = false,
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  defaultTab: string;
  mutateAll: () => void;
  summary?: {
    send_settings?: {
      delay_minutes?: number;
      dry_run?: boolean;
      mode?: string;
      pacing_mode?: "fixed_delay" | "spread_evenly";
      draft_scheduled_at?: string;
    };
    autopilot_schedule?: { day: string; cap: number; start: string; end: string }[];
    timezone?: string;
  };
  readOnly?: boolean;
}) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  const { authFetch } = useApiClient();

  // Send now / Schedule fields
  const [bulkDelay, setBulkDelay] = useState(5);
  const [scheduledAt, setScheduledAt] = useState("");
  const [dryRun, setDryRun] = useState(false);

  // Autopilot fields
  const [autoSchedule, setAutoSchedule] = useState<Record<string, { active: boolean; cap: string; start: string; end: string }>>({
    monday: { active: true, cap: "10", start: "09:00", end: "17:00" },
    tuesday: { active: true, cap: "10", start: "09:00", end: "17:00" },
    wednesday: { active: true, cap: "10", start: "09:00", end: "17:00" },
    thursday: { active: true, cap: "10", start: "09:00", end: "17:00" },
    friday: { active: true, cap: "10", start: "09:00", end: "17:00" },
    saturday: { active: false, cap: "10", start: "09:00", end: "17:00" },
    sunday: { active: false, cap: "10", start: "09:00", end: "17:00" },
  });
  const [autoDelay, setAutoDelay] = useState(5);
  const [autoPacing, setAutoPacing] = useState<"fixed_delay" | "spread_evenly">("fixed_delay");
  const [autoStartAt, setAutoStartAt] = useState("");
  const [timezone, setTimezone] = useState("UTC");

  const [sendingAction, setSendingAction] = useState(false);
  const [settingsReady, setSettingsReady] = useState(false);
  const [settingsError, setSettingsError] = useState("");

  const activeAutopilotEntries = Object.values(autoSchedule).filter((entry) => entry.active);
  const autopilotValidationError = activeAutopilotEntries.length === 0
    ? "Select at least one autopilot day."
    : activeAutopilotEntries.some(
        (entry) => Number(entry.cap) < 1 || !entry.start || !entry.end || entry.start >= entry.end
      )
      ? "Each enabled day needs a valid cap and a start time before its end time."
      : "";

  useEffect(() => {
    if (!isOpen || !summary) return;
    const hydration = window.setTimeout(() => {
      const settings = summary.send_settings || {};
      const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || summary.timezone || "UTC";
      setTimezone(readOnly ? summary.timezone || browserTimezone : browserTimezone);
      const savedMode = settings.mode || "send_now";
      setActiveTab(savedMode === "autopilot" ? "autopilot" : savedMode === "schedule" ? "schedule" : defaultTab);
      const savedDelay = Number(settings.delay_minutes ?? 5);
      setBulkDelay(savedDelay);
      setAutoDelay(savedDelay);
      setAutoPacing(settings.pacing_mode === "spread_evenly" ? "spread_evenly" : "fixed_delay");
      setDryRun(Boolean(settings.dry_run ?? false));
      if (settings.draft_scheduled_at) {
        const localValue = toLocalDateTimeInput(settings.draft_scheduled_at);
        setScheduledAt(localValue);
        setAutoStartAt(localValue);
      } else {
        setScheduledAt("");
        setAutoStartAt("");
      }
      if (summary.autopilot_schedule) {
        setAutoSchedule((current) => {
          const next = { ...current };
          for (const entry of summary.autopilot_schedule || []) {
            if (next[entry.day]) {
              next[entry.day] = {
                ...next[entry.day],
                active: true,
                cap: String(entry.cap),
                start: entry.start,
                end: entry.end,
              };
            }
          }
          for (const day of Object.keys(next)) {
            if (!(summary.autopilot_schedule || []).some((entry) => entry.day === day)) {
              next[day] = { ...next[day], active: false };
            }
          }
          return next;
        });
      }
      setSettingsReady(true);
    }, 0);
    return () => window.clearTimeout(hydration);
  }, [defaultTab, isOpen, readOnly, summary]);

  const saveSettings = useCallback(async (mode: "send_now" | "schedule" | "autopilot") => {
    const schedule: Record<string, { cap: number; start: string; end: string }> = {};
    if (mode === "autopilot") {
      for (const [day, config] of Object.entries(autoSchedule)) {
        if (config.active) schedule[day] = { cap: Number(config.cap), start: config.start, end: config.end };
      }
    }
    const draftDate = mode === "schedule" ? scheduledAt : mode === "autopilot" ? autoStartAt : "";
    const body: Record<string, unknown> = {
      mode,
      delay_minutes: mode === "autopilot" ? autoDelay : bulkDelay,
      dry_run: dryRun,
      timezone,
    };
    if (mode === "autopilot") {
      body.schedule = schedule;
      body.pacing_mode = autoPacing;
    }
    body.scheduled_at = draftDate ? new Date(draftDate).toISOString() : null;
    const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/send-settings`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Failed to save send settings");
  }, [authFetch, autoDelay, autoPacing, autoSchedule, autoStartAt, bulkDelay, campaignId, dryRun, scheduledAt, timezone]);

  useEffect(() => {
    if (!isOpen || readOnly || !settingsReady) return;
    const mode = activeTab === "autopilot" ? "autopilot" : activeTab === "schedule" ? "schedule" : "send_now";
    if (mode === "autopilot" && autopilotValidationError) return;
    const timer = window.setTimeout(() => {
      saveSettings(mode)
        .then(() => setSettingsError(""))
        .catch((error) => setSettingsError(errorMessage(error)));
    }, 600);
    return () => window.clearTimeout(timer);
  }, [activeTab, autopilotValidationError, isOpen, readOnly, saveSettings, settingsReady]);

  const finishClose = () => {
    setSettingsReady(false);
    mutateAll();
    onClose();
  };

  const closeDialog = async () => {
    if (!readOnly && settingsReady) {
      const mode = activeTab === "autopilot" ? "autopilot" : activeTab === "schedule" ? "schedule" : "send_now";
      if (!(mode === "autopilot" && autopilotValidationError)) {
        try {
          await saveSettings(mode);
        } catch (error) {
          setSettingsError(errorMessage(error));
          return;
        }
      }
    }
    finishClose();
  };

  const handleBulkSend = async (mode: "send-now" | "schedule") => {
    if (mode === "schedule" && !scheduledAt) {
      alert("Choose a start date and time.");
      return;
    }
    setSendingAction(true);
    try {
      const endpoint = mode === "send-now" ? "send-now" : "schedule";
      const body: Record<string, unknown> = { delay_minutes: bulkDelay, dry_run: dryRun };
      if (mode === "schedule" && scheduledAt) {
        body.scheduled_at = new Date(scheduledAt).toISOString();
      }
      console.log(`[Send] POST /api/campaigns/${campaignId}/${endpoint}`, body);
      const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      console.log(`[Send] Response ${res.status}:`, data);
      if (!res.ok) {
        throw new Error(data.detail?.msg || data.detail || "Failed");
      }
      finishClose();
    } catch (error: unknown) {
      console.error("[Send] Error:", errorMessage(error));
      alert(errorMessage(error));
    } finally {
      setSendingAction(false);
    }
  };

  const handleAutopilotStart = async () => {
    const scheduleBody: Record<string, { cap: number; start: string; end: string }> = {};
    for (const [day, config] of Object.entries(autoSchedule)) {
      if (config.active) {
        scheduleBody[day] = { cap: Number(config.cap), start: config.start, end: config.end };
      }
    }
    if (autopilotValidationError) {
      setSettingsError(autopilotValidationError);
      return;
    }
    setSendingAction(true);
    try {
      const body: Record<string, unknown> = {
        schedule: scheduleBody,
        delay_minutes: autoDelay,
        pacing_mode: autoPacing,
        dry_run: dryRun,
        timezone,
      };
      if (autoStartAt) {
        body.scheduled_at = new Date(autoStartAt).toISOString();
      }
      const res = await authFetch(`${API_URL}/api/campaigns/${campaignId}/autopilot/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail?.msg || data.detail || "Failed");
      }
      finishClose();
    } catch (error: unknown) {
      alert(errorMessage(error));
    } finally {
      setSendingAction(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) void closeDialog(); }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Send options</DialogTitle>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full pt-2">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="send-now">Send now</TabsTrigger>
            <TabsTrigger value="schedule">Schedule</TabsTrigger>
            <TabsTrigger value="autopilot">Autopilot</TabsTrigger>
          </TabsList>
          {(settingsError || (activeTab === "autopilot" ? autopilotValidationError : "")) && (
            <p className="mt-3 text-xs text-red-600">
              {settingsError || autopilotValidationError}
            </p>
          )}

          {/* 1. Send Now */}
          <TabsContent value="send-now" className="py-4 space-y-4">
            <p className="text-xs text-slate-500">
              Starts the next batch immediately using the connected senders in the selected group.
            </p>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Delay between emails (min)</label>
              <Input type="number" min={0} value={bulkDelay} onChange={(e) => setBulkDelay(Number(e.target.value))} disabled={readOnly} />
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} disabled={readOnly} className="accent-purple-600" />
              Test mode (no real emails sent)
            </label>
            <DialogFooter className="pt-2">
              <Button variant="outline" onClick={() => void closeDialog()}>Close</Button>
              {!readOnly && <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => handleBulkSend("send-now")} disabled={sendingAction}>
                {sendingAction ? "Starting..." : "Send now"}
              </Button>}
            </DialogFooter>
          </TabsContent>

          {/* 2. Schedule */}
          <TabsContent value="schedule" className="py-4 space-y-4">
            <p className="text-xs text-slate-500">
              Same as Send now, but starts at the date and time you pick.
            </p>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Delay between emails (min)</label>
              <Input type="number" min={0} value={bulkDelay} onChange={(e) => setBulkDelay(Number(e.target.value))} disabled={readOnly} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Start at</label>
              <Input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} disabled={readOnly} />
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} disabled={readOnly} className="accent-purple-600" />
              Test mode (no real emails sent)
            </label>
            <DialogFooter className="pt-2">
              <Button variant="outline" onClick={() => void closeDialog()}>Close</Button>
              {!readOnly && <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => handleBulkSend("schedule")} disabled={sendingAction || !scheduledAt}>
                {sendingAction ? "Scheduling..." : "Schedule"}
              </Button>}
            </DialogFooter>
          </TabsContent>

          {/* 3. Autopilot */}
          <TabsContent value="autopilot" className="py-4 space-y-4">
            <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
              <span>Configure per-day sending limits and time windows.</span>
              <span className="font-medium text-slate-700 shrink-0">{timezone}</span>
            </div>

            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map((d) => {
                const entry = autoSchedule[d];
                const dayLabel = d.charAt(0).toUpperCase() + d.slice(1, 3);
                return (
                  <div key={d} className="flex items-center gap-2 px-2 py-1.5 bg-slate-50 rounded-lg">
                    <input
                      type="checkbox"
                      checked={entry.active}
                      onChange={() =>
                        setAutoSchedule({
                          ...autoSchedule,
                          [d]: { ...entry, active: !entry.active },
                        })
                      }
                      disabled={readOnly}
                      className="w-4 h-4 shrink-0 accent-blue-600"
                    />
                    <span className="text-xs font-semibold text-slate-700 w-8 shrink-0">{dayLabel}</span>
                    <div className={`flex items-center gap-1.5 flex-1 ${entry.active ? "" : "opacity-40"}`}>
                      <Input
                        type="number"
                        min={1}
                        value={entry.cap}
                        onChange={(e) =>
                          setAutoSchedule({
                            ...autoSchedule,
                            [d]: { ...entry, cap: e.target.value },
                          })
                        }
                        disabled={readOnly || !entry.active}
                        className="h-7 w-16 text-xs"
                        placeholder="Emails"
                        title={`Emails to send on ${d}`}
                      />
                      <span className="text-xs text-slate-400 shrink-0">from</span>
                      <Input
                        type="time"
                        value={entry.start}
                        onChange={(e) =>
                          setAutoSchedule({
                            ...autoSchedule,
                            [d]: { ...entry, start: e.target.value },
                          })
                        }
                        disabled={readOnly || !entry.active}
                        className="h-7 w-24 text-xs"
                      />
                      <span className="text-xs text-slate-400 shrink-0">to</span>
                      <Input
                        type="time"
                        value={entry.end}
                        onChange={(e) =>
                          setAutoSchedule({
                            ...autoSchedule,
                            [d]: { ...entry, end: e.target.value },
                          })
                        }
                        disabled={readOnly || !entry.active}
                        className="h-7 w-24 text-xs"
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Pacing</label>
              <div className="grid grid-cols-2 gap-1 rounded-md bg-slate-100 p-1">
                <button
                  type="button"
                  aria-pressed={autoPacing === "fixed_delay"}
                  onClick={() => setAutoPacing("fixed_delay")}
                  disabled={readOnly}
                  className={`h-8 rounded px-3 text-xs font-medium transition-colors disabled:cursor-not-allowed ${
                    autoPacing === "fixed_delay"
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  Fixed delay
                </button>
                <button
                  type="button"
                  aria-pressed={autoPacing === "spread_evenly"}
                  onClick={() => setAutoPacing("spread_evenly")}
                  disabled={readOnly}
                  className={`h-8 rounded px-3 text-xs font-medium transition-colors disabled:cursor-not-allowed ${
                    autoPacing === "spread_evenly"
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  Spread evenly
                </button>
              </div>
            </div>

            {autoPacing === "fixed_delay" && (
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Delay between batches (min)</label>
                <Input type="number" min={0} value={autoDelay} onChange={(e) => setAutoDelay(Number(e.target.value))} disabled={readOnly} />
              </div>
            )}

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Start at (optional, leave empty to start now)</label>
              <Input type="datetime-local" value={autoStartAt} onChange={(e) => setAutoStartAt(e.target.value)} disabled={readOnly} />
            </div>

            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} disabled={readOnly} className="accent-purple-600" />
              Test mode (no real emails sent)
            </label>

            <DialogFooter className="pt-2">
              <Button variant="outline" onClick={() => void closeDialog()}>Close</Button>
              {!readOnly && <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={handleAutopilotStart} disabled={sendingAction}>
                {sendingAction ? "Starting..." : "Start Autopilot"}
              </Button>}
            </DialogFooter>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
