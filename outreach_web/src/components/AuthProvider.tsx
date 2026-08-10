"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { SWRConfig } from "swr";
import { toBackendProxyUrl } from "@/lib/api";

type AppUser = {
  fullName: string;
  email: string;
  publicMetadata: { role: "admin" };
};

type AppAuthState = {
  isLoaded: boolean;
  isSignedIn: boolean;
  user: AppUser | null;
  signOut: () => Promise<void>;
};

const AppAuthContext = createContext<AppAuthState | null>(null);

export function useAppAuth(): AppAuthState {
  const value = useContext(AppAuthContext);
  if (!value) throw new Error("useAppAuth must be used inside AuthProvider");
  return value;
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [user, setUser] = useState<AppUser | null>(null);

  useEffect(() => {
    fetch("/api/auth/session", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return null;
        return response.json() as Promise<{ authenticated: boolean; user?: AppUser }>;
      })
      .then((session) => {
        setIsSignedIn(Boolean(session?.authenticated));
        setUser(session?.user ?? null);
      })
      .catch(() => {
        setIsSignedIn(false);
        setUser(null);
      })
      .finally(() => setIsLoaded(true));
  }, []);

  const signOut = useCallback(async () => {
    await fetch("/api/auth/session", { method: "DELETE" });
    window.location.assign("/sign-in");
  }, []);

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

  const authState = useMemo(
    () => ({ isLoaded, isSignedIn, user, signOut }),
    [isLoaded, isSignedIn, user, signOut]
  );

  return (
    <AppAuthContext.Provider value={authState}>
      <SWRConfig value={swrConfig}>
        {children}
      </SWRConfig>
    </AppAuthContext.Provider>
  );
}
