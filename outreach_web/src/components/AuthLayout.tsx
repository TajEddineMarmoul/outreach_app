"use client";

import { useAuth } from "@clerk/nextjs";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useWelcomeComplete } from "@/lib/onboarding";
import AppHeader from "./AppHeader";
import "./app-ui.css";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isLoaded, isSignedIn, userId } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const welcomeComplete = useWelcomeComplete(userId);
  const isPublicPage = pathname === "/" || pathname === "/animation-lab";
  const isCampaignWorkspace = /^\/campaigns\/[^/]+\/?$/.test(pathname);

  useEffect(() => {
    if (isPublicPage || !isLoaded || !isSignedIn || !userId || welcomeComplete === null) return;
    if (pathname !== "/welcome" && !welcomeComplete) {
      router.replace("/welcome");
    }
  }, [isPublicPage, isLoaded, isSignedIn, userId, welcomeComplete, pathname, router]);

  if (isPublicPage) {
    return <main className="min-w-0 flex-1">{children}</main>;
  }

  if (isSignedIn && !welcomeComplete && pathname !== "/welcome") {
    return <main className="flex-1 bg-white" aria-label="Loading workspace" />;
  }

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
