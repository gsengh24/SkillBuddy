import Link from "next/link";
import type { ReactNode } from "react";

import { Avatar } from "@/components/ui/avatar";
import { BadgeDot } from "@/components/ui/badge";
import { BellIcon } from "@/components/ui/icons";
import { Logo } from "@/components/ui/logo";
import { StrengthBar } from "@/components/ui/strength-bar";
import { brand } from "@/lib/brand";

import { SidebarNav, TabBar } from "./nav";

export type ShellUser = { id: string; email: string };

type AppShellProps = {
  user: ShellUser;
  children: ReactNode;
  /** Optional 284px right rail, shown from 1280px up (it does not fit beside the sidebar
   * at 1024px). */
  rightRail?: ReactNode;
  unreadMessages?: number;
  hasNotifications?: boolean;
  /** Profile completeness, 0 to 100; null until profiles exist. */
  profileComplete?: number | null;
};

function BellLink({ hasNotifications }: { hasNotifications: boolean }) {
  return (
    <Link
      href="/notifications"
      aria-label={hasNotifications ? "Notifications (new)" : "Notifications"}
      className="border-line bg-paper text-ink hover:bg-green-chip relative inline-flex size-11 items-center justify-center rounded-full border"
    >
      <BellIcon />
      {hasNotifications ? <BadgeDot className="absolute top-2 right-2.5" /> : null}
    </Link>
  );
}

function ProfileCard({ value }: { value: number | null }) {
  return (
    <div className="rounded-card bg-amber-tint flex flex-col gap-2 p-4">
      <div className="text-small text-amber-ink flex items-baseline justify-between gap-2 font-bold">
        <span>Your profile</span>
        <span>{value === null ? "Not started" : `${value}%`}</span>
      </div>
      <StrengthBar value={value ?? 0} hue="amber" label="Profile complete" />
      <p className="text-small text-amber-ink">
        {value === null
          ? "Profiles open soon. You will say how you like to work, for sharper matches."
          : "Say how you like to work to get sharper matches."}
      </p>
    </div>
  );
}

/**
 * The signed-in app frame. Desktop (1024px+): 236px sidebar, main area, optional 284px
 * right rail. Phone: a top row (logo, bell) and a 64px bottom tab bar.
 */
export function AppShell({
  user,
  children,
  rightRail,
  unreadMessages = 0,
  hasNotifications = false,
  profileComplete = null,
}: AppShellProps) {
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[236px_minmax(0,1fr)]">
      <a
        href="#main"
        className="focus:border-ink focus:bg-paper sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-full focus:border focus:px-4 focus:py-2"
      >
        Skip to content
      </a>

      <aside className="border-line bg-paper hidden border-r px-5 py-7 lg:sticky lg:top-0 lg:flex lg:h-dvh lg:flex-col lg:gap-7">
        <Link href="/home" aria-label={`${brand.name} home`} className="self-start px-2">
          <Logo />
        </Link>
        <nav aria-label="Main">
          <SidebarNav unreadMessages={unreadMessages} />
        </nav>
        <ProfileCard value={profileComplete} />
        <Link
          href="/settings/account"
          aria-label="Your account"
          className="hover:bg-green-chip mt-auto flex min-h-11 items-center gap-3 rounded-xl px-2 py-1"
        >
          <Avatar userId={user.id} name={user.email} decorative />
          <span className="text-small text-ink min-w-0 truncate font-semibold">{user.email}</span>
        </Link>
      </aside>

      <div className="flex min-h-dvh min-w-0 flex-col">
        <header className="flex h-16 items-center justify-between px-4 lg:hidden">
          <Link href="/home" aria-label={`${brand.name} home`}>
            <Logo />
          </Link>
          <BellLink hasNotifications={hasNotifications} />
        </header>
        <div className="hidden justify-end px-10 pt-7 lg:flex">
          <BellLink hasNotifications={hasNotifications} />
        </div>

        <div className="flex-1 px-4 pt-2 pb-24 lg:px-10 lg:pb-10 xl:grid xl:grid-cols-[minmax(0,1fr)_284px] xl:gap-6">
          <main id="main" className="min-w-0">
            {children}
          </main>
          {rightRail ? (
            <aside aria-label="Side panel" className="hidden flex-col gap-4 xl:flex">
              {rightRail}
            </aside>
          ) : null}
        </div>

        <nav
          aria-label="Main"
          className="border-line bg-paper fixed inset-x-0 bottom-0 z-10 border-t lg:hidden"
        >
          <TabBar unreadMessages={unreadMessages} />
        </nav>
      </div>
    </div>
  );
}
