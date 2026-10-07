"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { TopBar } from "@/components/ds/page-parts";
import { cx } from "@/components/ui/cx";
import { MessageIcon } from "@/components/ui/icons";

import { APP_LINKS, DOT, ICON_LINK, isActive } from "./links";

/** The desktop top bar, with the current section marked (aria-current="page"). */
export function AppTopBar({ actions }: { actions: ReactNode }) {
  const pathname = usePathname();
  const current = APP_LINKS.find((link) => isActive(pathname, link.href));
  return (
    <TopBar homeHref="/home" links={[...APP_LINKS]} currentHref={current?.href} actions={actions} />
  );
}

/**
 * Messages has no tab of its own (Home takes it over in a later PR), so until then an icon
 * link keeps it one tap away, with a dot when there are unread messages.
 */
export function MessagesLink({ unread }: { unread: number }) {
  const current = isActive(usePathname(), "/messages");
  return (
    <Link
      href="/messages"
      aria-label={unread > 0 ? `Messages (${unread} unread)` : "Messages"}
      aria-current={current ? "page" : undefined}
      className={cx(ICON_LINK, current && "border-green text-green")}
    >
      <MessageIcon />
      {unread > 0 ? <span aria-hidden className={DOT} /> : null}
    </Link>
  );
}
