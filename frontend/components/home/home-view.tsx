import type { ReactNode } from "react";
import Link from "next/link";

import { ArrowLeftIcon } from "@/components/ds/icons";
import { Panel, TopicChip } from "@/components/ds/surfaces";
import { ButtonLink } from "@/components/ds/button";
import { TwoToneHeadline } from "@/components/ds/page-parts";
import { TextLink } from "@/components/ui/text-link";
import { cx } from "@/components/ui/cx";
import { summaryCounts, type ActivityRow, type Filter, type ItemType } from "@/lib/home/activity";
import type { Connection, MatchRequest } from "@/lib/api/schemas";

import { ActivityList } from "./activity-list";
import { EscapeToComposer } from "./escape-to-composer";
import { Greeting } from "./greeting";
import { LiveRefresh } from "./live-refresh";
import { HomeComposer } from "./home-composer";
import { SpacesBand, SummaryStrip } from "./parts";
import { TryAgain } from "./try-again";

/**
 * Home's whole layout: the ink inbox pane beside the composer or the opened item. It only
 * lays out what it is given (no fetching), so the page and the design previews share it.
 */
export function HomeView({
  email,
  hasProfile,
  failed,
  rows,
  filter,
  item,
  detail,
  lists,
}: {
  email: string;
  hasProfile: boolean;
  failed: boolean;
  rows: ActivityRow[];
  filter: Filter;
  item: { type: ItemType; id: string } | null;
  detail: ReactNode;
  lists: { requests: MatchRequest[]; connections: Connection[] };
}) {
  const composerHref = filter === "all" ? "/home" : `/home?filter=${filter}`;
  const hasConnections = lists.connections.length > 0;
  const needReply = rows.filter((row) => row.needsReply).length;
  const withMatches = rows.filter((row) => row.ready).length;
  const profile = hasProfile;
  const user = { email };

  return (
    <>
      <LiveRefresh fast={lists.requests.some((request) => request.status === "pending")} />
      <div className="border-line bg-card flex flex-col lg:-mx-4 lg:-mt-8 lg:grid lg:min-h-[min(820px,calc(100dvh-8rem))] lg:grid-cols-[360px_minmax(0,1fr)] lg:overflow-hidden lg:rounded-[18px] lg:border">
        <h1 className="sr-only">Home</h1>

        <aside
          aria-labelledby="inbox-h"
          className={cx(
            "bg-pane text-on-dark order-2 mt-4 flex flex-col gap-3.5 rounded-[18px] px-3.5 pt-5 pb-3.5 lg:order-1 lg:mt-0 lg:rounded-none lg:px-[18px] lg:pt-6 lg:pb-4",
            item && "hidden lg:flex",
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2
                id="inbox-h"
                className="font-display text-[26px] leading-none font-extrabold tracking-[-0.03em]"
              >
                Inbox
              </h2>
              <p className="text-on-dark-2 mt-1.5 text-[12.5px]">
                {needReply} {needReply === 1 ? "intro needs" : "intros need"} a reply ·{" "}
                {withMatches} {withMatches === 1 ? "request" : "requests"} with matches
              </p>
            </div>
            <Link
              href={`${composerHref}#new-request`}
              className="border-pane-line text-on-dark hover:border-on-dark-3 hover:bg-on-dark/5 inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3 text-[13px] font-medium whitespace-nowrap"
            >
              <span aria-hidden>+</span> New request
            </Link>
          </div>
          {failed ? (
            <TryAgain message="We couldn't load your activity just now." />
          ) : (
            <ActivityList
              rows={rows}
              initialFilter={filter}
              selectedKey={item ? `${item.type}-${item.id}` : null}
            />
          )}
        </aside>

        <section
          aria-label={item ? "Opened item" : "New request"}
          className={cx(
            "order-1 min-w-0 lg:order-2 lg:px-8 lg:pt-[72px] lg:pb-10",
            item && "lg:pt-8",
          )}
        >
          {item ? (
            <>
              <EscapeToComposer href={composerHref} />
              <TextLink
                href={composerHref}
                tone="muted"
                className="mb-1.5 inline-flex min-h-11 items-center gap-1.5 text-[15px] font-semibold lg:hidden"
              >
                <ArrowLeftIcon className="size-4" />
                Inbox
              </TextLink>
              <div className="mx-auto w-full max-w-[640px]">{detail}</div>
            </>
          ) : (
            <div
              id="new-request"
              className="mx-auto w-full max-w-[640px] scroll-mt-20 pt-2 lg:pt-0"
            >
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
                    A few lines about what you do and what you&apos;re looking for. We use it to
                    find people worth meeting.
                  </p>
                  <ButtonLink href="/onboarding" variant="primary" className="self-start">
                    Create your profile
                  </ButtonLink>
                </Panel>
              )}
              <div
                className={cx(
                  "mt-[22px] grid gap-3",
                  hasConnections ? "lg:grid-cols-2" : "hidden lg:grid",
                )}
              >
                <SummaryStrip counts={summaryCounts(lists)} className="hidden lg:grid" />
                {hasConnections ? <SpacesBand /> : null}
              </div>
            </div>
          )}
        </section>
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
