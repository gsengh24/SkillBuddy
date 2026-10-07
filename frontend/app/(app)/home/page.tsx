import type { Metadata } from "next";
import type { ReactNode } from "react";

import { RequestCard } from "@/components/discover/request-card";
import { ArrowLeftIcon } from "@/components/ds/icons";
import { Panel, TopicChip } from "@/components/ds/surfaces";
import { ButtonLink } from "@/components/ds/button";
import { TwoToneHeadline } from "@/components/ds/page-parts";
import { ActivityList } from "@/components/home/activity-list";
import { ChatDetail } from "@/components/home/chat-detail";
import { Greeting } from "@/components/home/greeting";
import { HomeComposer } from "@/components/home/home-composer";
import { NotAvailable, SpacesBand, StartFirstRequest, SummaryStrip } from "@/components/home/parts";
import { TryAgain } from "@/components/home/try-again";
import { IntroCard } from "@/components/social/intro-card";
import { TextLink } from "@/components/ui/text-link";
import { cx } from "@/components/ui/cx";
import { ApiError } from "@/lib/api/errors";
import type { Connection, Intro, MatchRequest, User } from "@/lib/api/schemas";
import { startEarly, withUser } from "@/lib/auth/with-user";
import { getConversation } from "@/lib/chat/server";
import {
  buildActivity,
  parseFilter,
  parseItem,
  summaryCounts,
  type ItemType,
} from "@/lib/home/activity";
import { getMyRequests } from "@/lib/matching/server";
import { getMyProfile } from "@/lib/profile/server";
import { getConnections, getReceivedIntros } from "@/lib/social/server";

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
    data: [profile, requestsOrNull, introPage, connectionList],
  } = await withUser(
    "/login?next=/home",
    Promise.all([
      getMyProfile(),
      orNull(getMyRequests()),
      orNull(getReceivedIntros()),
      orNull(getConnections()),
    ]),
  );

  // Without a profile there are no requests to list, whatever that call said.
  const requests = profile ? requestsOrNull : [];
  const intros = introPage?.items ?? null;
  const connections = connectionList?.items ?? null;
  const failed = requests === null || intros === null || connections === null;

  const lists = { requests: requests ?? [], intros: intros ?? [], connections: connections ?? [] };
  const rows = buildActivity(lists, new Date());
  const firstRequestHref = profile ? "#new-request" : "/onboarding";

  const detail = item ? await renderDetail(item, { user, ...lists, conversation }) : null;

  return (
    <div className="lg:grid lg:grid-cols-[400px_minmax(0,1fr)] lg:gap-8">
      <div
        className={cx("lg:border-line flex flex-col lg:border-r lg:pr-8", item && "hidden lg:flex")}
      >
        <h1 className="font-display text-[24px] leading-none font-extrabold tracking-[-0.05em]">
          Home
        </h1>
        <div className="pt-4 pb-4 lg:pt-0">
          <Greeting className="text-mono text-muted font-mono uppercase" />
          <TwoToneHeadline
            as="h2"
            lead="What are you building today?"
            rest="Say it in a sentence."
            size="greeting"
            className="mt-1.5"
          />
        </div>

        {profile ? (
          <div id="new-request" className="scroll-mt-20">
            <HomeComposer />
          </div>
        ) : (
          <Panel tone="green" className="flex flex-col gap-2">
            <TopicChip tone="soft" className="self-start">
              Start here
            </TopicChip>
            <p className="text-title-lg">Tell us about you</p>
            <p className="text-ink-2 max-w-md">
              A few lines about what you do and what you&apos;re looking for. We use it to find
              people worth meeting.
            </p>
            <ButtonLink href="/onboarding" variant="primary" className="self-start">
              Create your profile
            </ButtonLink>
          </Panel>
        )}

        <SummaryStrip counts={summaryCounts(lists)} />

        {failed ? (
          <TryAgain message="We couldn't load your activity just now." />
        ) : rows.length === 0 && filter === "all" ? (
          <StartFirstRequest href={firstRequestHref} className="lg:hidden" />
        ) : null}
        {failed ? null : (
          <ActivityList
            rows={rows}
            initialFilter={filter}
            selectedKey={item ? `${item.type}-${item.id}` : null}
          />
        )}

        {lists.connections.length ? <SpacesBand /> : null}

        <p className="text-meta-lg text-muted mt-6">
          You&apos;re signed in as <strong className="text-ink break-all">{user.email}</strong>.{" "}
          <TextLink href="/settings/account" tone="muted">
            Account settings
          </TextLink>
        </p>
      </div>

      <section
        aria-label={item ? "Opened item" : "Details"}
        className={cx("min-w-0", item ? "block" : "hidden lg:block")}
      >
        {item ? (
          <>
            <TextLink
              href="/home"
              tone="muted"
              className="text-meta-lg mb-4 inline-flex min-h-11 items-center gap-1.5 lg:hidden"
            >
              <ArrowLeftIcon className="size-4" />
              Back to Home
            </TextLink>
            {detail}
          </>
        ) : rows.length === 0 ? (
          <StartFirstRequest href={firstRequestHref} />
        ) : (
          <p className="text-muted py-6">Pick a request, an intro or a chat to open it here.</p>
        )}
      </section>
    </div>
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
