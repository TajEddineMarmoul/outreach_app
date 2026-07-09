"use client";

import { useAuth } from "@clerk/nextjs";
import { SWRConfig } from "swr";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const { getToken } = useAuth();

  const fetcher = async (url: string) => {
    const token = await getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error("API call failed");
    return res.json();
  };

  return (
    <SWRConfig value={{ fetcher, revalidateOnFocus: false, revalidateOnReconnect: false, shouldRetryOnError: false }}>
      {children}
    </SWRConfig>
  );
}
