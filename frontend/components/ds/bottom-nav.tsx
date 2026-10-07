"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";

import { isActive } from "../shell/nav";
import { cx } from "../ui/cx";

export type BottomNavItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
};

/**
 * The phone tab bar: four items, a 20px icon over a 10px label, the current one in green
 * (aria-current="page"), with padding for the home indicator. Hidden from 1024px up.
 */
export function BottomNav({ items, className }: { items: BottomNavItem[]; className?: string }) {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Main"
      className={cx(
        "border-line bg-bg sticky bottom-0 grid grid-cols-4 border-t px-1.5 pt-2 pb-[calc(10px+env(safe-area-inset-bottom))] lg:hidden",
        className,
      )}
    >
      {items.map(({ href, label, icon: Icon }) => {
        const current = isActive(pathname, href);
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
            <Icon />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
