import type { Metadata } from "next";
import type { ReactNode } from "react";

import { RequestCard } from "@/components/discover/request-card";
import { ChatDetail } from "@/components/home/chat-detail";
import { NotAvailable } from "@/components/home/parts";
import { IntroCard } from "@/components/social/intro-card";
import { ApiError } from "@/lib/api/errors";
import type { Connection, Intro, Match, MatchRequest, User } from "@/lib/api/schemas";
import { startEarly, withUser } from "@/lib/auth/with-user";
import { getConversation } from "@/lib/chat/server";
import { parseItem, type ItemType } from "@/lib/home/activity";
import { getRequest, getRequestMatches } from "@/lib/matching/server";
import { getConnections, getIntro } from "@/lib/social/server";

export const metadata: Metadata = { title: "Home" };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ item?: string | string[] }> };

type Item = { type: ItemType; id: string };

/** What the opened item needs, loaded by its own calls and nothing else. */
type Detail =
  | { type: "request"; request: MatchRequest | null; matches: Match[] | undefined }
  | { type: "intro"; intro: Intro | null }
  | {
      type: "chat";
      connection: Connection | undefined;
      conversation: Awaited<ReturnType<typeof getConversation>> | null;
    };

/** A call whose "not there" answer (404, or 403 for someone else's) is null, not an error. */
async function orNotFound<T>(call: Promise<T>): Promise<T | null> {
  try {
    return await call;
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 403)) return null;
    throw error;
  }
}

/**
 * The right side of Home: the item `?item=<type>-<id>` names, so back and refresh work. With
 * no item the layout shows the composer view and this renders nothing.
 *
 * Clicking a row in the inbox lands here and only here (the layout, with the lists, is not
 * re-run), so it costs the session check plus the item's own calls: a request and its
 * matches; an intro; or a chat's connection and messages. An item that is gone, or not this
 * person's, says so.
 */
export default async function HomePage({ searchParams }: Props) {
  const { item: raw } = await searchParams;
  const item = parseItem(Array.isArray(raw) ? raw[0] : raw);
  if (!item) return null;

  const { user, data } = await withUser("/login?next=/home", loadDetail(item));
  return renderDetail(user, data);
}

async function loadDetail(item: Item): Promise<Detail> {
  switch (item.type) {
    case "request": {
      const [request, matches] = await Promise.all([
        orNotFound(getRequest(item.id)),
        // Loaded with the request, so the card needs no second round trip from the browser.
        // If it fails the card asks for the matches itself, as it always did.
        getRequestMatches(item.id).catch(() => undefined),
      ]);
      return { type: "request", request, matches };
    }
    case "intro":
      return { type: "intro", intro: await orNotFound(getIntro(item.id)) };
    case "chat": {
      // Started with the connections and awaited only if the chat is this person's, as ever:
      // what the call says about a chat that is not theirs does not matter.
      const conversation = startEarly(orNotFound(getConversation(item.id)));
      const connection = (await getConnections()).items.find((c) => c.id === item.id);
      return { type: "chat", connection, conversation: connection ? await conversation : null };
    }
  }
}

function renderDetail(user: User, detail: Detail): ReactNode {
  switch (detail.type) {
    case "request":
      return detail.request ? (
        <RequestCard
          key={detail.request.id}
          initial={detail.request}
          initialMatches={detail.matches}
        />
      ) : (
        <NotAvailable />
      );
    case "intro":
      return detail.intro ? (
        <IntroCard key={detail.intro.id} initial={detail.intro} />
      ) : (
        <NotAvailable />
      );
    case "chat": {
      const { connection, conversation } = detail;
      if (!connection || !conversation) return <NotAvailable />;
      return (
        <ChatDetail
          key={connection.id}
          connection={connection}
          meId={user.id}
          page={conversation.page}
          cursor={conversation.cursor}
        />
      );
    }
  }
}
