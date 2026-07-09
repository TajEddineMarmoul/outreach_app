import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApiClient } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function ScheduleDialog({
  isOpen,
  onClose,
  campaignId,
  defaultTab,
  mutateAll,
  openRecipients
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  defaultTab: string;
  mutateAll: () => void;
  openRecipients: () => void;
}) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  const { authFetch } = useApiClient();

  // Send now / Schedule fields
  const [bulkDelay, setBulkDelay] = useState(5);
  const [scheduledAt, setScheduledAt] = useState("");

  // Autopilot fields
  const [days, setDays] = useState<string[]>(["monday", "tuesday", "wednesday", "thursday", "friday"]);
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("17:00");
  const [dailyCap, setDailyCap] = useState(10);
  const [autoDelay, setAutoDelay] = useState(5);
  const [autoStartAt, setAutoStartAt] = useState("");

  const [sendingAction, setSendingAction] = useState(false);

  useEffect(() => {
    setActiveTab(defaultTab);
  }, [defaultTab]);

  const handleBulkSend = async (mode: "send-now" | "schedule") => {
    setSendingAction(true);
    try {
      const endpoint = mode === "send-now" ? "send-now" : "schedule";
      const body: Record<string, unknown> = { delay_minutes: bulkDelay };
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
    } catch (err: any) {
      console.error("[Send] Error:", err.message);
      alert(err.message);
    } finally {
      setSendingAction(false);
    }
  };

  const handleAutopilotStart = async () => {
    setSendingAction(true);
    try {
      const body: Record<string, unknown> = {
        days,
        start_time: startTime,
        end_time: endTime,
        daily_cap: dailyCap,
        delay_minutes: autoDelay,
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
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSendingAction(false);
    }
  };

  const dayTitles: Record<string, string> = {
    monday: "M", tuesday: "T", wednesday: "W", thursday: "T",
    friday: "F", saturday: "S", sunday: "S",
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
              Sends all approved recipients immediately, one by one, with the delay below.
              No caps, no warmup, no time windows.
            </p>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Delay between emails (min)</label>
              <Input type="number" min={0} value={bulkDelay} onChange={(e) => setBulkDelay(Number(e.target.value))} />
            </div>
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
            <DialogFooter className="pt-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => handleBulkSend("schedule")} disabled={sendingAction}>
                {sendingAction ? "Scheduling..." : "Schedule"}
              </Button>
            </DialogFooter>
          </TabsContent>

          {/* 3. Autopilot */}
          <TabsContent value="autopilot" className="py-4 space-y-4">
            <p className="text-xs text-slate-500">
              Smart drip: respects warmup limits, daily caps, and sending windows.
              Spreads sends across days intelligently.
            </p>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-700">Sending days</label>
              <div className="flex gap-2">
                {["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map((d) => {
                  const active = days.includes(d);
                  return (
                    <button
                      type="button"
                      key={d}
                      onClick={() => {
                        if (active) setDays(days.filter((day) => day !== d));
                        else setDays([...days, d]);
                      }}
                      title={d}
                      className={`w-8 h-8 rounded text-xs font-bold transition-colors ${
                        active
                          ? "bg-blue-600 text-white"
                          : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                      }`}
                    >
                      {dayTitles[d]}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Sending window start</label>
                <Input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Sending window end</label>
                <Input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Daily cap</label>
                <Input type="number" min={1} value={dailyCap} onChange={(e) => setDailyCap(Number(e.target.value))} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Delay between emails (min)</label>
                <Input type="number" min={0} value={autoDelay} onChange={(e) => setAutoDelay(Number(e.target.value))} />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Start at (optional, leave empty to start now)</label>
              <Input type="datetime-local" value={autoStartAt} onChange={(e) => setAutoStartAt(e.target.value)} />
            </div>

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
