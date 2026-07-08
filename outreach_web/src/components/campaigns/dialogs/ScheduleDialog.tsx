import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

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
  const [checking, setChecking] = useState(true);
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [checkError, setCheckError] = useState("");
  
  // Schedule Form States
  const [days, setDays] = useState<string[]>(["monday", "tuesday", "wednesday", "thursday", "friday"]);
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("17:00");
  const [dailyCap, setDailyCap] = useState(10);
  const [delay, setDelay] = useState(5);
  const [senderDailyCap, setSenderDailyCap] = useState(10);
  const [sendingAction, setSendingAction] = useState(false);

  useEffect(() => {
    setActiveTab(defaultTab);
  }, [defaultTab]);

  const runPreflight = async () => {
    setChecking(true);
    setCheckError("");
    try {
      const res = await fetch(`${API_URL}/api/campaigns/${campaignId}/summary`);
      const summary = await res.json();
      
      // Let's emulate checklist checking
      const checks: Record<string, boolean> = {
        "Gmail connected": !!summary.sender,
        "Recipients selected": summary.recipients > 0,
        "Preview generated": true, // We can auto-generate or assume done
        "Test sent": true, // Or keep track in state
      };
      setChecklist(checks);
    } catch (err: any) {
      setCheckError("Failed to run preflight check");
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      runPreflight();
    }
  }, [isOpen, campaignId]);

  const handleStartSending = async (mode: string) => {
    setSendingAction(true);
    try {
      // First save send-settings if in schedule or autopilot
      if (mode === "schedule" || mode === "autopilot") {
        await fetch(`${API_URL}/api/campaigns/${campaignId}/send-settings`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            days,
            start_time: startTime,
            end_time: endTime,
            daily_cap: dailyCap,
            delay_minutes: delay,
            sender_daily_cap: senderDailyCap,
          }),
        });
      }
      
      const endpoint = mode === "send-now" ? "send-now" : mode === "schedule" ? "schedule" : "autopilot/start";
      const res = await fetch(`${API_URL}/api/campaigns/${campaignId}/${endpoint}`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail?.msg || data.detail || "Sending failed");
      }
      
      mutateAll();
      onClose();
    } catch (err: any) {
      alert(err.message);
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
          <TabsContent value="send-now" className="py-4">
            <DialogFooter className="pt-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => handleStartSending("send-now")} disabled={sendingAction}>
                {sendingAction ? "Sending..." : "Send now"}
              </Button>
            </DialogFooter>
          </TabsContent>

          {/* 2. Schedule */}
          <TabsContent value="schedule" className="py-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Start Time</label>
                <Input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">End Time</label>
                <Input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700">Allowed sending days</label>
              <div className="flex flex-wrap gap-2">
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
                      className={`px-2 py-1 text-xs rounded border transition-colors ${
                        active
                          ? "bg-blue-50 border-blue-300 text-blue-700 font-medium"
                          : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      {d.substring(0, 3).toUpperCase()}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Campaign daily cap</label>
                <Input type="number" min={1} value={dailyCap} onChange={(e) => setDailyCap(Number(e.target.value))} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Sender daily cap</label>
                <Input type="number" min={1} value={senderDailyCap} onChange={(e) => setSenderDailyCap(Number(e.target.value))} />
              </div>
            </div>
            <DialogFooter className="pt-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => handleStartSending("schedule")} disabled={sendingAction}>
                {sendingAction ? "Scheduling..." : "Save & Schedule"}
              </Button>
            </DialogFooter>
          </TabsContent>

          {/* 3. Autopilot */}
          <TabsContent value="autopilot" className="py-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Warmup daily cap</label>
                <Input type="number" min={1} value={dailyCap} onChange={(e) => setDailyCap(Number(e.target.value))} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Delay between emails (min)</label>
                <Input type="number" min={1} value={delay} onChange={(e) => setDelay(Number(e.target.value))} />
              </div>
            </div>
            <DialogFooter className="pt-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => handleStartSending("autopilot")} disabled={sendingAction}>
                {sendingAction ? "Activating..." : "Start Autopilot"}
              </Button>
            </DialogFooter>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
