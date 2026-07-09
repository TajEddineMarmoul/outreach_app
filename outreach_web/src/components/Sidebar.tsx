"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Mail, FileText, Users, BarChart2, Settings, Send, AtSign } from "lucide-react";
import { UserButton, useUser } from "@clerk/nextjs";
import { cn } from "@/lib/utils";
import { isAdminUser } from "@/lib/auth";

const menuItems = [
  { name: "Campaigns", href: "/campaigns", icon: Mail },
  { name: "Templates", href: "/templates", icon: FileText },
  { name: "Contacts", href: "/contacts", icon: Users },
  { name: "Senders", href: "/senders", icon: AtSign },
  { name: "Analytics", href: "/analytics", icon: BarChart2 },
  { name: "Settings", href: "/settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useUser();
  const isAdmin = isAdminUser(user);

  return (
    <aside className="w-72 border-r border-slate-200 bg-slate-50/80 backdrop-blur flex flex-col h-screen sticky top-0">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 border-b border-slate-200">
        <Link href="/campaigns" className="flex items-center gap-2 font-bold text-2xl text-slate-900">
          <Send className="w-6 h-6 text-blue-600" />
          <span>Outreach</span>
        </Link>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 py-6 px-4 space-y-1">
        {menuItems.map((item) => {
          const isActive = pathname.startsWith(item.href) || (item.href === "/campaigns" && pathname === "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-3 rounded-lg text-base font-medium transition-colors",
                isActive
                  ? "bg-blue-50 text-blue-600 font-semibold"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              )}
            >
              <Icon className={cn("w-5 h-5", isActive ? "text-blue-600" : "text-slate-400")} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>
      
      {/* Footer Info */}
      <div className="p-4 border-t border-slate-200">
        <div className="flex items-center gap-3">
          <UserButton />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-900 truncate flex items-center gap-1.5">
              {user?.fullName || user?.primaryEmailAddress?.emailAddress || "User"}
              {isAdmin && <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 border border-blue-200">Admin</span>}
            </p>
            <p className="text-xs text-slate-500 truncate">
              {user?.primaryEmailAddress?.emailAddress || ""}
            </p>
          </div>
        </div>
        <p className="text-xs text-slate-400 text-center mt-3">v1.0.0 &bull; Local Deployment</p>
      </div>
    </aside>
  );
}
