"use client";

import { useAuth } from "@clerk/nextjs";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://outreach-backend-166059707324.us-central1.run.app";

export function useApiClient() {
  const { getToken } = useAuth();

  const authFetch = async (url: string, options: RequestInit = {}) => {
    const token = await getToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return fetch(url, { ...options, headers });
  };

  return { API_URL, authFetch };
}
