"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useMemo } from "react";
import { SWRConfig } from "swr";
import { toBackendProxyUrl } from "@/lib/api";

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isSignedIn } = useAuth();

  useEffect(() => {
    if (!isSignedIn) return;
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!timezone) return;

    const syncTimezone = async () => {
      const response = await fetch(toBackendProxyUrl(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/settings/timezone`), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ timezone }),
      });
      if (!response.ok) {
        throw new Error(`Timezone sync failed with status ${response.status}`);
      }
    };

    void syncTimezone().catch((error) => console.error("[Timezone]", error));
  }, [isSignedIn]);

  const fetcher = useCallback(async (url: string) => {
    const res = await fetch(toBackendProxyUrl(url));
    if (!res.ok) throw new Error("API call failed");
    return res.json();
  }, []);
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
