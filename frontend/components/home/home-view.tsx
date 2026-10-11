import type { ReactNode } from "react";

import { Panel, TopicChip } from "@/components/ds/surfaces";
import { ButtonLink } from "@/components/ds/button";
import { TwoToneHeadline } from "@/components/ds/page-parts";
import { TextLink } from "@/components/ui/text-link";
import { cx } from "@/components/ui/cx";
import { summaryCounts, type ActivityRow } from "@/lib/home/activity";
import type { Connection, MatchRequest } from "@/lib/api/schemas";

import { DetailPane, InboxPane } from "./home-panes";
import { Greeting } from "./greeting";
import { LiveRefresh } from "./live-refresh";
import { HomeComposer } from "./home-composer";
import { SpacesBand, SummaryStrip } from "./parts";

/**
 * Home's frame, rendered by its layout: the ink inbox pane beside the composer or the opened
 * item. It only lays out what it is given (no fetching). `children` is the opened item, from
 * the page; the panes read `?item=` and `?filter=` from the address themselves.
 */
export function HomeView({
  email,
  hasProfile,
  failed,
  rows,
  lists,
  children,
}: {
  email: string;
  hasProfile: boolean;
  failed: boolean;
  rows: ActivityRow[];
  lists: { requests: MatchRequest[]; connections: Connection[] };
  children: ReactNode;
}) {
  const hasConnections = lists.connections.length > 0;
  const profile = hasProfile;
  const user = { email };

  const composer = (
    <div id="new-request" className="mx-auto w-full max-w-[640px] scroll-mt-20 pt-2 lg:pt-0">
      <Greeting className="text-green mt-[11px] font-mono text-[11px] leading-[1.4] font-medium tracking-[0.08em] uppercase" />
      <TwoToneHeadline
        as="h2"
        lead="What are you building today?"
        rest="Say it in a sentence."
        size="greeting"
        className="mt-2.5 mb-4 lg:mb-6"
      />
      {profile ? (
        <HomeComposer />
      ) : (
        <Panel tone="green" className="flex flex-col gap-2">
          <TopicChip tone="soft" className="self-start">
            Start here
          </TopicChip>
          <p className="text-title-lg">Tell us about you</p>
          <p className="text-ink-2 max-w-md">
            A few lines about what you do and what you&apos;re looking for. We use it to find people
            worth meeting.
          </p>
          <ButtonLink href="/onboarding" variant="primary" className="self-start">
            Create your profile
          </ButtonLink>
        </Panel>
      )}
      <div
        className={cx("mt-[22px] grid gap-3", hasConnections ? "lg:grid-cols-2" : "hidden lg:grid")}
      >
        <SummaryStrip counts={summaryCounts(lists)} className="hidden lg:grid" />
        {hasConnections ? <SpacesBand /> : null}
      </div>
    </div>
  );

  return (
    <>
      <LiveRefresh fast={lists.requests.some((request) => request.status === "pending")} />
      <div className="border-line bg-card flex flex-col lg:-mx-4 lg:-mt-8 lg:grid lg:min-h-[min(820px,calc(100dvh-8rem))] lg:grid-cols-[360px_minmax(0,1fr)] lg:overflow-hidden lg:rounded-[18px] lg:border">
        <h1 className="sr-only">Home</h1>
        <InboxPane rows={rows} failed={failed} />
        <DetailPane composer={composer}>{children}</DetailPane>
      </div>
      <p className="text-muted mt-4 text-[13px]">
        You&apos;re signed in as <strong className="text-ink break-all">{user.email}</strong>.{" "}
        <TextLink href="/you#s-security" tone="muted">
          Account settings
        </TextLink>
      </p>
    </>
  );
}
