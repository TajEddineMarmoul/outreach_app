"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Dialog as Drawer } from "@base-ui/react/dialog";
import {
  ArrowLeft,
  Menu,
  X,
  CircleHelp,
  Home,
  Layers,
  Users,
  FileText,
  ChartNoAxesColumn,
  Settings,
  AtSign,
} from "lucide-react";
import "@/components/campaigns/workspace/campaign-workspace.css";

const navigation = [
  { label: "Home", href: "/", icon: Home },
  { label: "Campaigns", href: "/campaigns", icon: Layers },
  { label: "Contacts", href: "/contacts", icon: Users },
  { label: "Templates", href: "/templates", icon: FileText },
  { label: "Senders", href: "/senders", icon: AtSign },
  { label: "Analytics", href: "/analytics", icon: ChartNoAxesColumn },
];

export default function AppMenu({
  onNavigate,
}: {
  onNavigate?: (href: string) => Promise<void>;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [help, setHelp] = useState(false);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (open) title.current?.focus();
  }, [open, help]);
  const navigate = (
    event: React.MouseEvent<HTMLAnchorElement>,
    href: string,
  ) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
      return;
    setOpen(false);
    setHelp(false);
    if (onNavigate) {
      event.preventDefault();
      void onNavigate(href);
    }
  };
  return (
    <Drawer.Root
      open={open}
      onOpenChange={(value) => {
        setOpen(value);
        if (!value) setHelp(false);
      }}
    >
      <Drawer.Trigger className="campaign-button campaign-menu-trigger">
        <Menu size={20} /> Menu
      </Drawer.Trigger>
      <Drawer.Portal>
        <Drawer.Backdrop className="campaign-drawer-backdrop" />
        <Drawer.Popup className="campaign-ui campaign-drawer">
          <div className="campaign-drawer-heading">
            <Drawer.Title ref={title} tabIndex={-1}>
              {help ? "Help" : "Menu"}
            </Drawer.Title>
            <Drawer.Close className="campaign-text-button">
              Close menu <X size={20} />
            </Drawer.Close>
          </div>
          <Drawer.Description className="sr-only">
            {help
              ? "Help using Outreach."
              : "Navigate to another part of Outreach."}
          </Drawer.Description>
          {help ? (
            <section className="campaign-help">
              <button
                className="campaign-text-button"
                onClick={() => setHelp(false)}
              >
                <ArrowLeft size={18} /> Back to menu
              </button>
              <h3>Your campaign, step by step</h3>
              <p>
                Choose an audience, write your message, connect senders, and set
                a schedule. Review everything before you launch.
              </p>
              <h3>Extra tools when you need them</h3>
              <p>
                Open the menus beside Add or More for imports, exports, and
                other options. Preview shows an unsent example of your message.
              </p>
              <h3>Control sending</h3>
              <p>
                While running, pause sending from Overview. Emails already
                sending may finish.
              </p>
            </section>
          ) : (
            <>
              <nav aria-label="Application navigation">
                {navigation.map(({ label, href, icon: Icon }) => (
                  <Link
                    key={href}
                    href={href}
                    aria-current={
                      (
                        href === "/"
                          ? pathname === "/"
                          : pathname.startsWith(href)
                      )
                        ? "page"
                        : undefined
                    }
                    onClick={(event) => navigate(event, href)}
                  >
                    <Icon size={23} strokeWidth={1.6} />
                    {label}
                  </Link>
                ))}
              </nav>
              <div className="campaign-drawer-footer">
                <Link
                  className="campaign-drawer-settings"
                  href="/settings"
                  aria-current={pathname === "/settings" ? "page" : undefined}
                  onClick={(event) => navigate(event, "/settings")}
                >
                  <Settings size={23} strokeWidth={1.6} /> Settings
                </Link>
                <button
                  className="campaign-drawer-help"
                  onClick={() => setHelp(true)}
                >
                  <CircleHelp size={23} strokeWidth={1.6} /> Help
                </button>
              </div>
            </>
          )}
        </Drawer.Popup>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
