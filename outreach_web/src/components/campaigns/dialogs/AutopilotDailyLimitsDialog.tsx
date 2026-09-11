"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Loader2, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { API_URL, checkResponse, errorMessage, useApiClient } from "@/lib/api";

export interface AutopilotScheduleDay {
  day: string;
  cap: number;
  start: string;
  end: string;
}

interface DailyCapacity {
  cap: number | null;
  sent: number | null;
  reserved: number | null;
  remaining: number | null;
}

function dayLabel(day: string) {
  return `${day.slice(0, 1).toUpperCase()}${day.slice(1)}`;
}

function limitProblem(value: string): string | null {
  const limit = Number(value);
  if (!Number.isInteger(limit) || limit < 1) {
    return "Use a whole number of at least 1.";
  }
  return null;
}

export default function AutopilotDailyLimitsDialog({
  isOpen,
  onClose,
  campaignId,
  schedule,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  schedule: AutopilotScheduleDay[];
  onSaved: () => void | Promise<unknown>;
}) {
  const { authFetch } = useApiClient();
  const [limits, setLimits] = useState<Record<string, string>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [capacity, setCapacity] = useState<DailyCapacity | null>(null);
  const [loadingCapacity, setLoadingCapacity] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const timer = window.setTimeout(() => {
      setLimits(
        Object.fromEntries(schedule.map((entry) => [entry.day, String(entry.cap)])),
      );
      setFieldErrors({});
      setError("");
      setSaved(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isOpen, schedule]);

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    const timer = window.setTimeout(() => {
      setLoadingCapacity(true);
      void (async () => {
        try {
          const progress = await checkResponse<{
            campaign_daily_cap: number | null;
            campaign_sent_today: number | null;
            campaign_reserved_today: number | null;
            campaign_remaining_today: number | null;
          }>(
            await authFetch(`${API_URL}/api/campaigns/${campaignId}/send-progress`),
            "Couldn’t load today’s sending capacity.",
          );
          if (!active) return;
          setCapacity({
            cap: progress.campaign_daily_cap,
            sent: progress.campaign_sent_today,
            reserved: progress.campaign_reserved_today,
            remaining: progress.campaign_remaining_today,
          });
        } catch {
          // Capacity is supplementary here; saving still reports a meaningful error if needed.
          if (active) setCapacity(null);
        } finally {
          if (active) setLoadingCapacity(false);
        }
      })();
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [authFetch, campaignId, isOpen]);

  const validation = useMemo(
    () =>
      Object.fromEntries(
        schedule
          .map((entry) => [entry.day, limitProblem(limits[entry.day] ?? "")])
          .filter(([, problem]) => problem),
      ) as Record<string, string>,
    [limits, schedule],
  );

  const updateLimit = (day: string, value: string) => {
    setLimits((current) => ({ ...current, [day]: value }));
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[day];
      return next;
    });
    setError("");
    setSaved(false);
  };

  const validateLimit = (day: string) => {
    const problem = limitProblem(limits[day] ?? "");
    setFieldErrors((current) => {
      if (!problem) {
        const next = { ...current };
        delete next[day];
        return next;
      }
      return { ...current, [day]: problem };
    });
  };

  const save = async () => {
    if (Object.keys(validation).length > 0) {
      setFieldErrors(validation);
      return;
    }
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const result = await checkResponse<{
        capacity?: {
          cap: number;
          sent: number;
          reserved: number;
          remaining: number;
        } | null;
      }>(
        await authFetch(
          `${API_URL}/api/campaigns/${campaignId}/autopilot/daily-limits`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              daily_limits: Object.fromEntries(
                schedule.map((entry) => [entry.day, Number(limits[entry.day])]),
              ),
            }),
          },
        ),
        "Couldn’t update Autopilot’s daily limits.",
      );
      if (result.capacity) {
        setCapacity({
          cap: result.capacity.cap,
          sent: result.capacity.sent,
          reserved: result.capacity.reserved,
          remaining: Math.max(result.capacity.remaining, 0),
        });
      }
      await onSaved();
      setSaved(true);
    } catch (saveError) {
      setError(errorMessage(saveError, "Couldn’t update Autopilot’s daily limits."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Adjust daily email limits</DialogTitle>
          <DialogDescription>
            These limits take effect while Autopilot keeps running. Your
            message, audience, senders, and sending window stay protected
            until you pause the campaign.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <section
            className="rounded-lg border border-blue-100 bg-blue-50/70 p-3"
            aria-live="polite"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-slate-800">
              <Send className="size-4 text-blue-700" />
              Today&apos;s campaign capacity
            </div>
            {loadingCapacity ? (
              <p className="mt-2 flex items-center gap-2 text-sm text-slate-600">
                <Loader2 className="size-4 animate-spin" /> Loading capacity…
              </p>
            ) : capacity?.cap != null ? (
              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
                <div>
                  <dt className="text-slate-500">Limit</dt>
                  <dd className="font-semibold text-slate-900">{capacity.cap}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Sent</dt>
                  <dd className="font-semibold text-slate-900">{capacity.sent ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Scheduled</dt>
                  <dd className="font-semibold text-slate-900">{capacity.reserved ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Available</dt>
                  <dd className="font-semibold text-blue-800">{capacity.remaining ?? 0}</dd>
                </div>
              </dl>
            ) : (
              <p className="mt-2 text-sm text-slate-600">
                There is no Autopilot limit set for today.
              </p>
            )}
          </section>

          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            {schedule.map((entry) => {
              const fieldError = fieldErrors[entry.day];
              return (
                <div key={entry.day} className="grid grid-cols-[1fr_7rem] items-start gap-3">
                  <label htmlFor={`autopilot-limit-${entry.day}`} className="pt-2 text-sm font-medium text-slate-800">
                    {dayLabel(entry.day)}
                    <span className="mt-0.5 block text-xs font-normal text-slate-500">
                      {entry.start}–{entry.end}
                    </span>
                  </label>
                  <div>
                    <Input
                      id={`autopilot-limit-${entry.day}`}
                      type="number"
                      min={1}
                      step={1}
                      inputMode="numeric"
                      aria-describedby={fieldError ? `autopilot-limit-${entry.day}-error` : undefined}
                      aria-invalid={Boolean(fieldError)}
                      value={limits[entry.day] ?? ""}
                      onChange={(event) => updateLimit(entry.day, event.target.value)}
                      onBlur={() => validateLimit(entry.day)}
                    />
                    {fieldError && (
                      <p id={`autopilot-limit-${entry.day}-error`} className="mt-1 text-xs text-red-600" role="alert">
                        {fieldError}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </form>

          {error && <p className="text-sm text-red-600" role="alert">{error}</p>}
          {saved && (
            <p className="flex items-center gap-2 text-sm text-emerald-700" role="status">
              <CheckCircle2 className="size-4" /> Daily limits saved. Autopilot is still running.
            </p>
          )}
        </div>

        <DialogFooter showCloseButton>
          <Button type="button" onClick={() => void save()} disabled={saving || schedule.length === 0}>
            {saving && <Loader2 className="animate-spin" />}
            {saving ? "Saving limits…" : "Save daily limits"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
