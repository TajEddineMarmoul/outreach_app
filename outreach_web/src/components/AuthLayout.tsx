"use client";

import { useAppAuth } from "./AuthProvider";
import Sidebar from "./Sidebar";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAppAuth();

  if (!isLoaded) {
    return <main className="flex-1 min-h-screen bg-slate-50" />;
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
      <Sidebar />
      <main className="flex-1 flex flex-col h-screen overflow-y-auto">
        {children}
      </main>
    </>
  );
}
