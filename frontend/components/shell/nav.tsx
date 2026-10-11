"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Logo } from "@/components/ds/logo";
import { cx } from "@/components/ui/cx";

import { APP_LINKS, currentPlace } from "./links";

/**
 * The app header: logo on the left, the three places as a pill switcher in the middle (from
 * 1024px up; phones use the bottom nav), and the bell and account on the right. The
 * current place is marked with aria-current="page".
 */
export function AppHeader({ actions }: { actions: ReactNode }) {
  const current = currentPlace(usePathname());
  return (
    <header className="max-w-content mx-auto flex w-full items-center justify-between gap-4 px-4 pt-[calc(14px+env(safe-area-inset-top))] pb-3.5 lg:px-8">
      <Link href="/home" aria-label="Cynergi home" className="rounded-control">
        <Logo />
      </Link>
      <nav
        aria-label="Main"
        className="bg-panel border-line hidden gap-1 rounded-full border p-1 lg:flex"
      >
        {APP_LINKS.map(({ href, label }) => {
          const isCurrent = href === current?.href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={isCurrent ? "page" : undefined}
              className={cx(
                "rounded-full px-[18px] py-2 text-[14px] font-medium",
                isCurrent ? "bg-ink text-bg" : "text-muted hover:text-ink",
              )}
            >
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="flex items-center gap-2">{actions}</div>
    </header>
  );
}
