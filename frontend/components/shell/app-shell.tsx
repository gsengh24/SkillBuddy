import Link from "next/link";
import type { ReactNode } from "react";

import { Avatar } from "@/components/ds/avatar";
import { BottomNav } from "@/components/ds/bottom-nav";
import { BellIcon, HomeIcon, PeopleIcon, YouIcon } from "@/components/ds/icons";
import { Logo } from "@/components/ds/logo";
import { cx } from "@/components/ui/cx";

import { APP_LINKS, DOT, ICON_LINK } from "./links";
import { AppTopBar } from "./nav";

export type ShellUser = { id: string; email: string };

type AppShellProps = {
  user: ShellUser;
  children: ReactNode;
  /** Optional 284px right rail, shown from 1280px up. */
  rightRail?: ReactNode;
  hasNotifications?: boolean;
  /** Profile completeness, 0 to 100; null when the user has no profile yet. */
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

/** How complete the profile is, linking to it (or to onboarding before there is one). */
function ProfileProgress({ value }: { value: number | null }) {
  return (
    <Link
      href={value === null ? "/onboarding" : "/you"}
      className="rounded-control text-meta-lg text-ink hover:bg-panel flex min-h-11 items-center gap-2 px-2"
    >
      <span>Your profile</span>
      <span
        role="meter"
        aria-label="Profile complete"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value ?? 0}
        className="bg-green-tint border-green-line h-1.5 w-12 overflow-hidden rounded-full border"
      >
        <span className="bg-green block h-full" style={{ width: `${value ?? 0}%` }} />
      </span>
      <span className="text-muted font-mono text-[11px]">
        {value === null ? "Not started" : `${value}%`}
      </span>
    </Link>
  );
}

/**
 * The signed-in app frame (ADR 0014). Desktop (1024px+): the top bar with Home, Spaces
 * and You, plus profile progress, the bell and the account. Phone: a slim top row
 * (logo, bell) and the bottom nav with the same three places. Chats count as Home.
 */
export function AppShell({
  user,
  children,
  rightRail,
  hasNotifications = false,
  profileComplete = null,
}: AppShellProps) {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="focus:border-ink focus:bg-bg rounded-control sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:border focus:px-4 focus:py-2"
      >
        Skip to content
      </a>

      <div className="max-w-content mx-auto hidden w-full px-8 lg:block">
        <AppTopBar
          actions={
            <>
              <ProfileProgress value={profileComplete} />
              <BellLink hasNotifications={hasNotifications} />
              <Link
                href="/you#s-security"
                aria-label="Your account"
                title={user.email}
                className="inline-flex size-11 items-center justify-center rounded-full"
              >
                <Avatar userId={user.id} name={user.email} decorative />
              </Link>
            </>
          }
        />
      </div>

      <header className="border-line flex h-14 items-center justify-between gap-3 border-b px-4 lg:hidden">
        <Link href="/home" className="rounded-control inline-flex min-h-11 items-center">
          <Logo />
        </Link>
        <BellLink hasNotifications={hasNotifications} />
      </header>

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
