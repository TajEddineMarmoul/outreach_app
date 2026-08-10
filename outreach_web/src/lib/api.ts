"use client";

import { useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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
