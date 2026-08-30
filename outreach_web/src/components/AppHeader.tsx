"use client";

import Link from "next/link";
import { UserButton } from "@clerk/nextjs";
import AppMenu from "./AppMenu";

export default function AppHeader() {
  return (
    <header className="app-header campaign-ui">
      <Link href="/campaigns" className="campaign-brand">
        OUTREACH
      </Link>
      <AppMenu />
      <div className="app-account">
        <UserButton
          appearance={{ elements: { avatarBox: { width: 36, height: 36 } } }}
        />
      </div>
    </header>
  );
}
