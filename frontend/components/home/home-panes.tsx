"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { ArrowLeftIcon } from "@/components/ds/icons";
import { cx } from "@/components/ui/cx";
import { TextLink } from "@/components/ui/text-link";
import { parseFilter, parseItem, type ActivityRow } from "@/lib/home/activity";

import { ActivityList } from "./activity-list";
import { EscapeToComposer } from "./escape-to-composer";
import { TryAgain } from "./try-again";

/**
 * What the address says: which item is open, and which tab it asks for. The panes read it
 * here instead of being handed it by the page. The inbox lives in Home's layout, which stays
 * as it is when only `?item=` changes, so opening another item re-renders just the detail.
 */
function useHomeUrl() {
  const params = useSearchParams();
  const filter = parseFilter(params.get("filter") ?? undefined);
  return {
    item: parseItem(params.get("item") ?? undefined),
    filter,
    composerHref: filter === "all" ? "/home" : `/home?filter=${filter}`,
  };
}

/** The ink inbox pane: its heading and counts, "New request", and the list (or its error state). */
export function InboxPane({ rows, failed }: { rows: ActivityRow[]; failed: boolean }) {
  const { item, filter, composerHref } = useHomeUrl();
  const needReply = rows.filter((row) => row.needsReply).length;
  const withMatches = rows.filter((row) => row.ready).length;

  return (
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
            {needReply} {needReply === 1 ? "intro needs" : "intros need"} a reply · {withMatches}{" "}
            {withMatches === 1 ? "request" : "requests"} with matches
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
  );
}

/**
 * The right side: the composer view, or the opened item (what the page rendered). On phones
 * an opened item covers the whole screen, with a way back to the inbox.
 */
export function DetailPane({ composer, children }: { composer: ReactNode; children: ReactNode }) {
  const { item, composerHref } = useHomeUrl();

  return (
    <section
      aria-label={item ? "Opened item" : "New request"}
      className={cx("order-1 min-w-0 lg:order-2 lg:px-8 lg:pt-[72px] lg:pb-10", item && "lg:pt-8")}
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
          <div className="mx-auto w-full max-w-[640px]">{children}</div>
        </>
      ) : (
        composer
      )}
    </section>
  );
}
