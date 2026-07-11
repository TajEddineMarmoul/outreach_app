import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}

export default function ScheduleDialog({
  isOpen,
  onClose,
  campaignId,
  defaultTab,
  mutateAll,
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  defaultTab: string;
  mutateAll: () => void;
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
  const [autoStartAt, setAutoStartAt] = useState("");

  const [sendingAction, setSendingAction] = useState(false);

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
      mutateAll();
      onClose();
    } catch (error: unknown) {
      console.error("[Send] Error:", errorMessage(error));
      alert(errorMessage(error));
    } finally {
      setSendingAction(false);
    }
  };

  const handleAutopilotStart = async () => {
    setSendingAction(true);
    try {
      const scheduleBody: Record<string, { cap: number; start: string; end: string }> = {};
      for (const [day, config] of Object.entries(autoSchedule)) {
        if (config.active) {
          scheduleBody[day] = { cap: Number(config.cap), start: config.start, end: config.end };
        }
      }
      const body: Record<string, unknown> = {
        schedule: scheduleBody,
        delay_minutes: autoDelay,
        dry_run: dryRun,
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
      mutateAll();
      onClose();
    } catch (error: unknown) {
      alert(errorMessage(error));
    } finally {
      setSendingAction(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
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

          {/* 1. Send Now */}
          <TabsContent value="send-now" className="py-4 space-y-4">
            <p className="text-xs text-slate-500">
              Starts the next batch immediately using the connected senders in the selected group.
            </p>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Delay between emails (min)</label>
              <Input type="number" min={0} value={bulkDelay} onChange={(e) => setBulkDelay(Number(e.target.value))} />
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} className="accent-purple-600" />
              Test mode (no real emails sent)
            </label>
            <DialogFooter className="pt-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => handleBulkSend("send-now")} disabled={sendingAction}>
                {sendingAction ? "Starting..." : "Send now"}
              </Button>
            </DialogFooter>
          </TabsContent>

          {/* 2. Schedule */}
          <TabsContent value="schedule" className="py-4 space-y-4">
            <p className="text-xs text-slate-500">
              Same as Send now, but starts at the date and time you pick.
            </p>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Delay between emails (min)</label>
              <Input type="number" min={0} value={bulkDelay} onChange={(e) => setBulkDelay(Number(e.target.value))} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Start at</label>
              <Input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} className="accent-purple-600" />
              Test mode (no real emails sent)
            </label>
            <DialogFooter className="pt-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => handleBulkSend("schedule")} disabled={sendingAction || !scheduledAt}>
                {sendingAction ? "Scheduling..." : "Schedule"}
              </Button>
            </DialogFooter>
          </TabsContent>

          {/* 3. Autopilot */}
          <TabsContent value="autopilot" className="py-4 space-y-4">
            <p className="text-xs text-slate-500">
              Configure per-day sending limits and time windows.
              Days with no checkmark are skipped.
            </p>

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
                        disabled={!entry.active}
                        className="h-7 w-16 text-xs"
                        placeholder="Cap"
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
                        disabled={!entry.active}
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
                        disabled={!entry.active}
                        className="h-7 w-24 text-xs"
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Delay between batches (min)</label>
              <Input type="number" min={0} value={autoDelay} onChange={(e) => setAutoDelay(Number(e.target.value))} />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Start at (optional, leave empty to start now)</label>
              <Input type="datetime-local" value={autoStartAt} onChange={(e) => setAutoStartAt(e.target.value)} />
            </div>

            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} className="accent-purple-600" />
              Test mode (no real emails sent)
            </label>

            <DialogFooter className="pt-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={handleAutopilotStart} disabled={sendingAction}>
                {sendingAction ? "Starting..." : "Start Autopilot"}
              </Button>
            </DialogFooter>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
