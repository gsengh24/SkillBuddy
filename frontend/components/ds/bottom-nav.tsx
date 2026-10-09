"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { isActive } from "../shell/links";
import { cx } from "../ui/cx";

export type BottomNavItem = {
  href: string;
  label: string;
  /** An icon element, e.g. <HomeIcon />. (An element, not a component: server pages pass these.) */
  icon: ReactNode;
  /** Other paths that belong to this item (e.g. chats belong to Home). */
  match?: readonly string[];
};

/**
 * The phone tab bar: equal-width items, a 20px icon over a 10px label, the current one in green
 * (aria-current="page"), with padding for the home indicator. Hidden from 1024px up.
 */
export function BottomNav({ items, className }: { items: BottomNavItem[]; className?: string }) {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Main"
      className={cx(
        "border-line bg-bg sticky bottom-0 grid auto-cols-fr grid-flow-col border-t px-1.5 pt-2 pb-[calc(10px+env(safe-area-inset-bottom))] lg:hidden",
        className,
      )}
    >
      {items.map(({ href, label, icon, match = [] }) => {
        const current = [href, ...match].some((path) => isActive(pathname, path));
        return (
          <Link
            key={href}
            href={href}
            aria-current={current ? "page" : undefined}
            className={cx(
              "rounded-control flex min-h-11 flex-col items-center justify-center gap-0.5 text-[10px]",
              current ? "text-green font-medium" : "text-muted hover:text-ink",
            )}
          >
            {icon}
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
