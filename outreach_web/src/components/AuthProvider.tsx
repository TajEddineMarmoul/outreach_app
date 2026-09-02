"use client";

import { useAuth } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useMemo } from "react";
import { SWRConfig } from "swr";
import { toBackendProxyUrl } from "@/lib/api";

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isSignedIn } = useAuth();
  const isPublicHome = usePathname() === "/";

  useEffect(() => {
    if (!isSignedIn || isPublicHome) return;
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!timezone) return;

    const syncTimezone = async () => {
      try {
        const response = await fetch(toBackendProxyUrl(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/settings/timezone`), {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ timezone, only_if_unset: true }),
        });
        if (!response.ok && process.env.NODE_ENV === "development") {
          console.warn(`[Timezone] Background sync skipped (status ${response.status}).`);
        }
      } catch {
        if (process.env.NODE_ENV === "development") {
          console.warn("[Timezone] Background sync skipped because the backend is unavailable.");
        }
      }
    };

    void syncTimezone();
  }, [isSignedIn, isPublicHome]);

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
