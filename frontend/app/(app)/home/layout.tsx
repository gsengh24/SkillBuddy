import type { ReactNode } from "react";

import { HomeView } from "@/components/home/home-view";
import { withUser } from "@/lib/auth/with-user";
import { buildActivity } from "@/lib/home/activity";
import { getMyRequests } from "@/lib/matching/server";
import { getMyProfile } from "@/lib/profile/server";
import { getConnections, getReceivedIntros, getSentIntros } from "@/lib/social/server";

export const dynamic = "force-dynamic";

/** A list call that may fail on its own: null means "show the error state". */
function orNull<T>(call: Promise<T>): Promise<T | null> {
  return call.catch(() => null);
}

/**
 * Home's frame and inbox (design spec 6.2): requests, intros and messages in one list, newest
 * first, beside the composer or the opened item. The page (`page.tsx`) renders only what is
 * open on the right.
 *
 * The lists live here, not in the page, on purpose: a layout is not re-rendered when only
 * `?item=` changes, so opening another item does not re-fetch them. They are fetched on a
 * first visit, on `router.refresh()` (`LiveRefresh`, and `notifyHomeChanged` after anything
 * that changes them), and never again on a click.
 *
 * The lists use /auth/me, /me/profile, /requests, /intros?box=received|sent and /connections,
 * all at once (the shell adds /notifications/unread-count).
 */
export default async function HomeLayout({ children }: { children: ReactNode }) {
  const {
    user,
    data: [profile, requestsOrNull, introPage, sentPage, connectionList],
  } = await withUser(
    "/login?next=/home",
    Promise.all([
      getMyProfile(),
      orNull(getMyRequests()),
      orNull(getReceivedIntros()),
      orNull(getSentIntros()),
      orNull(getConnections()),
    ]),
  );

  // Without a profile there are no requests to list, whatever that call said.
  const requests = profile ? requestsOrNull : [];
  const intros = introPage && sentPage ? [...introPage.items, ...sentPage.items] : null;
  const connections = connectionList?.items ?? null;
  const failed = requests === null || intros === null || connections === null;

  const lists = { requests: requests ?? [], intros: intros ?? [], connections: connections ?? [] };
  const rows = buildActivity(lists, new Date());

  return (
    <HomeView
      email={user.email}
      hasProfile={Boolean(profile)}
      failed={failed}
      rows={rows}
      lists={lists}
    >
      {children}
    </HomeView>
  );
}
