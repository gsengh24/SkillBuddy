"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";

import { Badge, BadgeDot } from "@/components/ui/badge";
import { cx } from "@/components/ui/cx";
import { BookmarkIcon, CompassIcon, MessageIcon, PersonIcon } from "@/components/ui/icons";

type NavItem = {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  showsUnread?: boolean;
};

const DISCOVER: NavItem = { label: "Discover", href: "/home", icon: CompassIcon };
const MESSAGES: NavItem = {
  label: "Messages",
  href: "/messages",
  icon: MessageIcon,
  showsUnread: true,
};
const SAVED: NavItem = { label: "Saved", href: "/saved", icon: BookmarkIcon };
const YOU: NavItem = { label: "You", href: "/profile", icon: PersonIcon };

export const SIDEBAR_ITEMS = [DISCOVER, MESSAGES, SAVED];
export const TAB_ITEMS = [DISCOVER, MESSAGES, SAVED, YOU];

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Desktop sidebar navigation (1024px and up). */
export function SidebarNav({ unreadMessages = 0 }: { unreadMessages?: number }) {
  const pathname = usePathname();
  return (
    <ul className="flex flex-col gap-1">
      {SIDEBAR_ITEMS.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cx(
                "text-body flex h-11 items-center justify-between rounded-xl px-3",
                active
                  ? "bg-green-tint text-green-ink font-bold"
                  : "text-ink hover:bg-green-chip font-medium",
              )}
            >
              {item.label}
              {item.showsUnread ? <Badge count={unreadMessages} label="unread messages" /> : null}
            </Link>
          </li>
        );
      })}
      <li>
        <span
          aria-disabled="true"
          className="text-body text-muted flex h-11 cursor-not-allowed items-center gap-2 px-3"
        >
          Pair spaces
          <span className="font-mono text-[10px] font-medium tracking-[0.1em] uppercase">Soon</span>
        </span>
      </li>
    </ul>
  );
}

/** Phone bottom tab bar: 64px high, each tab at least 44px wide and tall. */
export function TabBar({ unreadMessages = 0 }: { unreadMessages?: number }) {
  const pathname = usePathname();
  return (
    <ul className="grid h-16 grid-cols-4">
      {TAB_ITEMS.map((item) => {
        const active = isActive(pathname, item.href);
        const Icon = item.icon;
        return (
          <li key={item.href} className="flex">
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cx(
                "flex min-h-11 min-w-11 flex-1 flex-col items-center justify-center gap-1 text-[12px]",
                active ? "text-green-ink font-bold" : "text-muted hover:text-ink font-medium",
              )}
            >
              <span className="relative">
                <Icon />
                {item.showsUnread && unreadMessages > 0 ? (
                  <BadgeDot
                    label={`${unreadMessages} unread messages`}
                    className="absolute -top-0.5 -right-1"
                  />
                ) : null}
              </span>
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
