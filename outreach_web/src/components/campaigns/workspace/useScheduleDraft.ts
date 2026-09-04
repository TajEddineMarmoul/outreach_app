"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL, responseProblem, useApiClient } from "@/lib/api";
import {
  hydrateSchedule,
  schedulePayload,
  scheduleProblem,
  type SavedSchedule,
  type ScheduleDraft,
} from "./scheduleDraft";

export default function useScheduleDraft(
  campaignId: string,
  summary: SavedSchedule | undefined,
  locked: boolean,
) {
  const { authFetch } = useApiClient();
  const [draft, setDraft] = useState<ScheduleDraft | null>(null);
  const [configured, setConfigured] = useState(false);
  const [status, setStatus] = useState<
    "saved" | "unsaved" | "saving" | "error"
  >("saved");
  const [error, setError] = useState("");
  const current = useRef<ScheduleDraft | null>(null);
  const hydrated = useRef("");
  const savedKey = useRef("");
  const queuedKey = useRef("");
  const queue = useRef<Promise<void>>(Promise.resolve());
  const pending = useRef<Promise<void>>(Promise.resolve());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!summary || hydrated.current === campaignId) return;
    const value = hydrateSchedule(summary);
    hydrated.current = campaignId;
    current.current = value;
    savedKey.current = JSON.stringify(value);
    queuedKey.current = savedKey.current;
    setDraft(value);
    setConfigured(Boolean(summary.send_settings?.mode));
    setStatus("saved");
    setError("");
  }, [campaignId, summary]);

  const update = useCallback((value: ScheduleDraft) => {
    current.current = value;
    setDraft(value);
    setStatus(
      JSON.stringify(value) === savedKey.current &&
        queuedKey.current === savedKey.current
        ? "saved"
        : "unsaved",
    );
    setError("");
  }, []);

  const flush = useCallback(
    async (force = false) => {
      if (timer.current) {
        clearTimeout(timer.current);
        timer.current = null;
      }
      if (locked) return;
      const value = current.current;
      if (!value)
        throw new Error("The schedule is still loading. Please try again.");
      const key = JSON.stringify(value);
      if (!force && key === savedKey.current) {
        await pending.current.catch(() => undefined);
        if (key === savedKey.current) {
          setStatus("saved");
          setError("");
          return;
        }
      }
      const problem = scheduleProblem(value);
      if (problem) {
        setError(problem);
        throw new Error(problem);
      }
      if (key === queuedKey.current && key !== savedKey.current) {
        await pending.current;
        return;
      }
      queuedKey.current = key;
      const operation = queue.current.then(async () => {
        setStatus("saving");
        const response = await authFetch(
          `${API_URL}/api/campaigns/${campaignId}/send-settings`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(schedulePayload(value)),
          },
        );
        if (!response.ok)
          throw new Error(
            responseProblem(
              await response.json().catch(() => ({})),
              "Could not save your schedule. Please retry.",
            ),
          );
        savedKey.current = key;
        setConfigured(true);
        setStatus(
          JSON.stringify(current.current) === key ? "saved" : "unsaved",
        );
        setError("");
      });
      pending.current = operation;
      queue.current = operation.catch(() => undefined);
      try {
        await operation;
      } catch (error) {
        if (queuedKey.current === key) {
          queuedKey.current = savedKey.current;
          setStatus("error");
          setError(
            error instanceof Error ? error.message : "Could not save schedule.",
          );
        }
        throw error;
      }
    },
    [authFetch, campaignId, locked],
  );

  useEffect(() => {
    if (
      !draft ||
      locked ||
      (JSON.stringify(draft) === savedKey.current &&
        queuedKey.current === savedKey.current) ||
      scheduleProblem(draft)
    )
      return;
    timer.current = setTimeout(() => {
      void flush().catch(() => undefined);
    }, 700);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [draft, flush, locked]);

  return {
    draft,
    update,
    configured,
    status,
    error,
    flush,
    problem: draft ? scheduleProblem(draft) : "Schedule is loading.",
  };
}
