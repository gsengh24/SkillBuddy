import Link from "next/link";
import type { ReactNode } from "react";

import { Avatar } from "@/components/ds/avatar";
import { BottomNav } from "@/components/ds/bottom-nav";
import { BellIcon, HomeIcon, PeopleIcon, YouIcon } from "@/components/ds/icons";
import { cx } from "@/components/ui/cx";

import { APP_LINKS, DOT, ICON_LINK } from "./links";
import { AppHeader } from "./nav";

export type ShellUser = { id: string; email: string };

type AppShellProps = {
  user: ShellUser;
  children: ReactNode;
  /** Optional 284px right rail, shown from 1280px up. */
  rightRail?: ReactNode;
  hasNotifications?: boolean;
  /**
   * Profile completeness, 0 to 100; null before there is a profile. The Home header design
   * has no progress meter, so the shell no longer shows it (the You page still does).
   */
  profileComplete?: number | null;
};

const ICONS: Record<(typeof APP_LINKS)[number]["href"], ReactNode> = {
  "/home": <HomeIcon />,
  "/spaces": <PeopleIcon />,
  "/you": <YouIcon />,
};

const BOTTOM_NAV_ITEMS = APP_LINKS.map((link) => ({ ...link, icon: ICONS[link.href] }));

function BellLink({ hasNotifications }: { hasNotifications: boolean }) {
  return (
    <Link
      href="/notifications"
      aria-label={hasNotifications ? "Notifications (new)" : "Notifications"}
      className={ICON_LINK}
    >
      <BellIcon />
      {hasNotifications ? <span aria-hidden className={DOT} /> : null}
    </Link>
  );
}

/**
 * The signed-in app frame (ADR 0014, Home reference). One header: logo, the Home / Spaces /
 * You pill switcher from 1024px up, the bell and the account. Phones get the bottom nav
 * with the same three places. Chats count as Home.
 */
export function AppShell({ user, children, rightRail, hasNotifications = false }: AppShellProps) {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="focus:border-ink focus:bg-bg rounded-control sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:border focus:px-4 focus:py-2"
      >
        Skip to content
      </a>

      <AppHeader
        actions={
          <>
            <BellLink hasNotifications={hasNotifications} />
            <Link
              href="/you#s-security"
              aria-label="Your account"
              title={user.email}
              className="inline-flex size-11 items-center justify-center rounded-full"
            >
              <Avatar
                userId={user.id}
                name={user.email}
                decorative
                className="size-11! text-[15px]"
              />
            </Link>
          </>
        }
      />

      <div
        className={cx(
          "max-w-content mx-auto w-full flex-1 px-4 pt-4 pb-8 lg:px-8 lg:pt-8",
          rightRail ? "xl:grid xl:grid-cols-[minmax(0,1fr)_284px] xl:gap-6" : null,
        )}
      >
        <main id="main" className="min-w-0">
          {children}
        </main>
        {rightRail ? (
          <aside aria-label="Side panel" className="hidden flex-col gap-4 xl:flex">
            {rightRail}
          </aside>
        ) : null}
      </div>

      <BottomNav items={BOTTOM_NAV_ITEMS} className="z-10" />
    </div>
  );
}
