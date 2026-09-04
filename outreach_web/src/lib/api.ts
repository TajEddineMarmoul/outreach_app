"use client";

import { useCallback } from "react";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const DEFAULT_REQUEST_ERROR = "Something went wrong. Please try again.";

export function responseProblem(
  data: unknown,
  fallback = DEFAULT_REQUEST_ERROR,
): string {
  if (!data || typeof data !== "object") return fallback;

  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const { message, msg } = detail as {
      message?: unknown;
      msg?: unknown;
    };
    if (typeof message === "string") return message;
    if (typeof msg === "string") return msg;
  }

  return fallback;
}

export async function checkResponse<T = Record<string, unknown>>(
  response: Response,
  fallback = "We couldn’t save this change. Please try again.",
): Promise<T> {
  const data: unknown = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(responseProblem(data, fallback));
  return data as T;
}

export function errorMessage(
  error: unknown,
  fallback = DEFAULT_REQUEST_ERROR,
): string {
  return error instanceof Error ? error.message : fallback;
}

export function toBackendProxyUrl(url: string): string {
  try {
    const requested = new URL(url);
    const backend = new URL(API_URL);
    if (requested.origin === backend.origin) {
      return `/api/backend${requested.pathname}${requested.search}`;
    }
  } catch {
    // Relative application URLs do not need proxying.
  }
  return url;
}

export function useApiClient() {
  const authFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    return fetch(toBackendProxyUrl(url), { ...options, credentials: "same-origin" });
  }, []);

  return { API_URL, authFetch };
}
