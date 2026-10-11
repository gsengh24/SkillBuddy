import type { Metadata } from "next";
import type { ReactNode } from "react";

import { RequestCard } from "@/components/discover/request-card";
import { ChatDetail } from "@/components/home/chat-detail";
import { HomeView } from "@/components/home/home-view";
import { NotAvailable } from "@/components/home/parts";
import { IntroCard } from "@/components/social/intro-card";
import { ApiError } from "@/lib/api/errors";
import type { Connection, Intro, MatchRequest, User } from "@/lib/api/schemas";
import { startEarly, withUser } from "@/lib/auth/with-user";
import { getConversation } from "@/lib/chat/server";
import { buildActivity, parseFilter, parseItem, type ItemType } from "@/lib/home/activity";
import { getMyRequests } from "@/lib/matching/server";
import { getMyProfile } from "@/lib/profile/server";
import { getConnections, getReceivedIntros, getSentIntros } from "@/lib/social/server";

export const metadata: Metadata = { title: "Home" };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ item?: string; filter?: string }> };

/** A list call that may fail on its own: null means "show the error state". */
function orNull<T>(call: Promise<T>): Promise<T | null> {
  return call.catch(() => null);
}

/**
 * Home (design spec 6.2): requests, intros and messages in one list, newest first, with the
 * composer above it. Desktop shows the opened item on the right; phones show it full screen
 * with a back arrow. `?item=<type>-<id>` says what is open, so back and refresh work;
 * `?filter=messages` (where /messages now leads) preselects the Messages filter.
 *
 * The list uses /auth/me, /me/profile, /requests, /intros?box=received and /connections,
 * all at once (the shell adds /notifications/unread-count). An open item uses what its own
 * screen always used: a chat loads its messages, a request its matches.
 */
export default async function HomePage({ searchParams }: Props) {
  const params = await searchParams;
  const item = parseItem(params.item);
  const filter = parseFilter(params.filter);

  const conversation = item?.type === "chat" ? startEarly(getConversation(item.id)) : null;
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
  const detail = item ? await renderDetail(item, { user, ...lists, conversation }) : null;

  return (
    <HomeView
      email={user.email}
      hasProfile={Boolean(profile)}
      failed={failed}
      rows={rows}
      filter={filter}
      item={item}
      detail={detail}
      lists={lists}
    />
  );
}

async function renderDetail(
  item: { type: ItemType; id: string },
  {
    user,
    requests,
    intros,
    connections,
    conversation,
  }: {
    user: User;
    requests: MatchRequest[];
    intros: Intro[];
    connections: Connection[];
    conversation: ReturnType<typeof getConversation> | null;
  },
): Promise<ReactNode> {
  switch (item.type) {
    case "request": {
      const request = requests.find((r) => r.id === item.id);
      return request ? <RequestCard key={request.id} initial={request} /> : <NotAvailable />;
    }
    case "intro": {
      const intro = intros.find((i) => i.id === item.id);
      return intro ? <IntroCard key={intro.id} initial={intro} /> : <NotAvailable />;
    }
    case "chat": {
      const connection = connections.find((c) => c.id === item.id);
      if (!connection || !conversation) return <NotAvailable />;
      const loaded = await conversation.catch((error: unknown) => {
        // Gone or not theirs: say so. Anything else is a real failure (error.tsx).
        if (error instanceof ApiError && (error.status === 404 || error.status === 403))
          return null;
        throw error;
      });
      if (!loaded) return <NotAvailable />;
      return (
        <ChatDetail
          key={connection.id}
          connection={connection}
          meId={user.id}
          page={loaded.page}
          cursor={loaded.cursor}
        />
      );
    }
  }
}
