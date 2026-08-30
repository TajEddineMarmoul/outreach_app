"use client";

import { useAuth } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import AppHeader from "./AppHeader";
import "./app-ui.css";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isSignedIn } = useAuth();
  const pathname = usePathname();
  const isCampaignWorkspace = /^\/campaigns\/[^/]+\/?$/.test(pathname);

  if (!isSignedIn) {
    return (
      <main className="flex-1 flex flex-col h-screen overflow-y-auto">
        {children}
      </main>
    );
  }

  return (
    <>
      <main
        className={`min-w-0 flex-1 flex flex-col h-dvh overflow-y-auto ${!isCampaignWorkspace ? "app-ui app-shell" : ""}`}
      >
        {!isCampaignWorkspace && <AppHeader />}
        {children}
      </main>
    </>
  );
}
