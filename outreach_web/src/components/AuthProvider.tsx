"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useMemo } from "react";
import { SWRConfig } from "swr";

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const { getToken } = useAuth();

  const fetcher = useCallback(async (url: string) => {
    const token = await getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error("API call failed");
    return res.json();
  }, [getToken]);
  const swrConfig = useMemo(
    () => ({ fetcher, revalidateOnFocus: false, revalidateOnReconnect: false, shouldRetryOnError: false }),
    [fetcher]
  );

  return (
    <SWRConfig value={swrConfig}>
      {children}
    </SWRConfig>
  );
}
