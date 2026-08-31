"use client";

import { useSyncExternalStore } from "react";

export type GuideStep = "audience" | "message" | "review";
const GUIDE_STEPS: GuideStep[] = ["audience", "message", "review"];

const key = (userId: string, name: string) => `outreach:${userId}:onboarding-v1:${name}`;
const memory = new Map<string, string>();
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => { listeners.delete(listener); window.removeEventListener("storage", listener); };
}

function read(userId: string, name: string): string | null {
  try {
    return window.localStorage.getItem(key(userId, name));
  } catch {
    return memory.get(key(userId, name)) ?? null;
  }
}

function write(userId: string, name: string, value: string): void {
  memory.set(key(userId, name), value);
  try {
    window.localStorage.setItem(key(userId, name), value);
  } catch {
    // The app remains usable when browser storage is unavailable.
  }
  listeners.forEach((listener) => listener());
}

export function hasCompletedWelcome(userId: string): boolean {
  return read(userId, "welcome") === "complete";
}

export function completeWelcome(userId: string): void {
  write(userId, "welcome", "complete");
}

function readCampaignTips(userId: string): string {
  const tips = read(userId, "tips");
  if (tips !== null) return tips;

  // Keep existing dismissals when moving from the numbered guide to independent tips.
  const previousStep = GUIDE_STEPS.indexOf(read(userId, "guide") as GuideStep);
  return previousStep < 0 ? "" : GUIDE_STEPS.slice(previousStep).join(",");
}

export function showCampaignTips(userId: string): void {
  write(userId, "tips", GUIDE_STEPS.join(","));
}

export function hideCampaignTips(userId: string): void {
  write(userId, "tips", "");
}

export function dismissCampaignTip(userId: string, step: GuideStep): void {
  write(userId, "tips", readCampaignTips(userId).split(",").filter((tip) => tip !== step).join(","));
}

export function useWelcomeComplete(userId: string | null | undefined): boolean | null {
  return useSyncExternalStore(subscribe, () => userId ? hasCompletedWelcome(userId) : false, () => null);
}

export function useCampaignTips(userId: string | null | undefined): GuideStep[] {
  const tips = useSyncExternalStore(subscribe, () => userId ? readCampaignTips(userId) : "", () => "");
  return GUIDE_STEPS.filter((step) => tips.split(",").includes(step));
}
