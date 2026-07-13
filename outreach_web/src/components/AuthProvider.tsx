"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useMemo } from "react";
import { SWRConfig } from "swr";

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn } = useAuth();

  useEffect(() => {
    if (!isSignedIn) return;
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!timezone) return;

    const syncTimezone = async () => {
      const token = await getToken();
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/settings/timezone`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ timezone }),
      });
      if (!response.ok) {
        throw new Error(`Timezone sync failed with status ${response.status}`);
      }
    };

    void syncTimezone().catch((error) => console.error("[Timezone]", error));
  }, [getToken, isSignedIn]);

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
