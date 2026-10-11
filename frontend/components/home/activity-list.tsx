"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";

import { Avatar } from "@/components/ds/avatar";
import { QuickRespond } from "@/components/home/quick-respond";
import { cx } from "@/components/ui/cx";
import { itemHref, type ActivityRow, type Filter } from "@/lib/home/activity";

type Sub = "mine" | "intros";

/** What an empty list says, per filter, with the picture that goes with it. */
const EMPTY: Record<Filter, { image: string; title: string; text: string; start: boolean }> = {
  all: {
    image: "/art/home/home_empty_inbox.jpg",
    title: "No requests yet.",
    text: "Describe what you're building and we'll find people.",
    start: true,
  },
  requests: {
    image: "/art/home/home_empty_inbox.jpg",
    title: "No requests yet.",
    text: "Describe what you're building and we'll find people.",
    start: true,
  },
  messages: {
    image: "/art/home/home_no_chats.jpg",
    title: "No chats yet.",
    text: "Accept an intro, or have one of yours accepted, and a chat opens here.",
    start: false,
  },
};

const TILE =
  "bg-on-dark/6 border-on-dark/8 text-on-dark inline-flex size-[38px] items-center justify-center rounded-[10px] border [&_svg]:size-[17px]";

/** The reference's row icons: 20px, 1.6 stroke. */
function RowIcon({ children, join }: { children: ReactNode; join?: boolean }) {
  return (
    <svg
      aria-hidden
      focusable="false"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin={join ? "round" : undefined}
    >
      {children}
    </svg>
  );
}

function Tile({ row }: { row: ActivityRow }) {
  if (row.type === "chat" && row.person) {
    return (
      <Avatar
        userId={row.person.userId}
        name={row.person.name}
        photoUrl={row.person.photoUrl}
        decorative
        tone="pane"
        className="size-[38px] text-[14px] font-semibold"
      />
    );
  }
  if (row.type === "intro" && !row.sent) {
    return (
      <span className={cx(TILE, "border-on-dark-3 border-dashed bg-transparent")}>
        <RowIcon>
          <circle cx="8" cy="7" r="3" />
          <path d="M2.5 16.5c.6-3 2.8-4.5 5.5-4.5s4.9 1.5 5.5 4.5M15.5 6v5M13 8.5h5" />
        </RowIcon>
      </span>
    );
  }
  if (row.type === "intro") {
    return (
      <span className={TILE}>
        <RowIcon join>
          <path d="M3 10 17 3l-4 14-3-6z" />
        </RowIcon>
      </span>
    );
  }
  return (
    <span className={TILE}>
      <RowIcon>
        <circle cx="9" cy="9" r="5.5" />
        <path d="m13.2 13.2 3.8 3.8" />
      </RowIcon>
    </span>
  );
}

function InboxRow({
  row,
  selected,
  onAnswered,
}: {
  row: ActivityRow;
  selected: boolean;
  onAnswered: () => void;
}) {
  return (
    <li className="flex items-center">
      <Link
        href={itemHref(row.type, row.id)}
        aria-current={selected ? "true" : undefined}
        className={cx(
          "hover:bg-on-dark/5 grid min-h-14 min-w-0 flex-1 grid-cols-[38px_minmax(0,1fr)_auto] items-start gap-3 rounded-[10px] px-2.5 py-[11px]",
          selected && "bg-mint/10 hover:bg-mint/10 shadow-[inset_2px_0_var(--mint)]",
        )}
      >
        <span aria-hidden className="shrink-0">
          <Tile row={row} />
        </span>
        <span className="min-w-0">
          <span className="text-on-dark-3 mb-[3px] flex items-center gap-1.5 font-mono text-[10px] leading-[1.3] tracking-[0.08em] uppercase">
            {row.needsReply ? (
              <>
                {row.kind} · <span className="text-amber">Needs a reply</span>
              </>
            ) : (
              row.kind
            )}
          </span>
          <span className="text-on-dark block truncate text-[14px] font-semibold">{row.title}</span>
          <span
            className={cx(
              "mt-0.5 block truncate text-[12.5px]",
              row.ready ? "text-mint-text" : "text-on-dark-2",
            )}
          >
            {row.secondary}
          </span>
        </span>
        <span className="text-on-dark-3 mt-1 grid justify-items-end gap-2 font-mono text-[11px] leading-none whitespace-nowrap">
          <span>{row.time}</span>
          {row.unread ? (
            <span className="bg-mint inline-block size-2 rounded-full">
              <span className="sr-only">Unread messages</span>
            </span>
          ) : null}
        </span>
      </Link>
      {row.type === "intro" && !row.sent ? (
        <QuickRespond introId={row.id} onAnswered={onAnswered} />
      ) : null}
    </li>
  );
}

function Count({ children, on }: { children: number; on: boolean }) {
  return (
    <b
      className={cx(
        "ml-[5px] inline-grid h-[18px] min-w-[18px] place-items-center rounded-[9px] px-[5px] font-mono text-[10.5px] leading-none font-medium",
        on ? "bg-mint text-pane" : "bg-on-dark/12",
      )}
    >
      {children}
    </b>
  );
}

/**
 * The inbox list on the ink pane: the All / Requests / Messages filter (Requests splits into
 * your requests and the intros you were sent), then one list, newest first, grouped Today
 * and Earlier. Filtering happens here, without a reload; the open item stays selected.
 */
export function ActivityList({
  rows,
  initialFilter,
  selectedKey,
}: {
  rows: ActivityRow[];
  initialFilter: Filter;
  selectedKey: string | null;
}) {
  const [filter, setFilter] = useState<Filter>(initialFilter);
  const [sub, setSub] = useState<Sub>("mine");
  const [answered, setAnswered] = useState<string[]>([]);
  const requestRows = rows.filter((row) => row.group === "requests");
  const count = {
    all: rows.length,
    requests: requestRows.length,
    messages: rows.filter((row) => row.group === "messages").length,
    mine: requestRows.filter((row) => row.sub === "mine").length,
    intros: requestRows.filter((row) => row.sub === "intros").length,
  };
  const shown = (
    filter === "all"
      ? rows
      : filter === "messages"
        ? rows.filter((row) => row.group === "messages")
        : requestRows.filter((row) => row.sub === sub)
  ).filter((row) => !answered.includes(row.key));
  const empty = EMPTY[filter];

  // On desktop the right side is never left blank behind a list: choosing a tab opens its
  // newest item (unless the open one is already in it). Phones keep the list, since an
  // open item covers the whole screen there. Also runs once for /messages, which lands on
  // the Messages tab. The composer stays one click away: "New request" clears the item
  // without changing the tab, so nothing re-opens.
  const router = useRouter();
  const openFirst = useRef(initialFilter !== "all");
  const first = shown[0];
  const selectedShown = shown.some((row) => row.key === selectedKey);
  useEffect(() => {
    if (!openFirst.current || !first) return;
    openFirst.current = false;
    if (selectedShown || !window.matchMedia("(min-width: 1024px)").matches) return;
    router.replace(itemHref(first.type, first.id));
  }, [first, selectedShown, router]);
  const choose = (next: () => void) => {
    openFirst.current = true;
    next();
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3.5">
      <div role="group" aria-label="Filter" className="bg-on-dark/5 flex gap-1 rounded-full p-1">
        {(
          [
            ["all", "All"],
            ["requests", "Requests"],
            ["messages", "Messages"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={filter === value}
            onClick={() => choose(() => setFilter(value))}
            className={cx(
              "min-h-11 flex-1 rounded-full px-1.5 py-2 text-[13px] whitespace-nowrap pointer-fine:min-h-[38px]",
              filter === value ? "bg-on-dark/10 text-on-dark" : "text-on-dark-2 hover:text-on-dark",
            )}
          >
            {label} <Count on={filter === value}>{count[value]}</Count>
          </button>
        ))}
      </div>

      {filter === "requests" ? (
        <div
          role="group"
          aria-label="Show"
          className="border-pane-line flex gap-[18px] border-b px-1"
        >
          {(
            [
              ["mine", "Your requests"],
              ["intros", "Intros"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={sub === value}
              onClick={() => choose(() => setSub(value))}
              className={cx(
                "-mb-px min-h-9 border-b-[1.5px] pb-[9px] text-[12.5px]",
                sub === value
                  ? "border-mint text-on-dark"
                  : "text-on-dark-3 hover:text-on-dark border-transparent",
              )}
            >
              {label}{" "}
              <b className="text-on-dark-3 ml-[5px] font-mono text-[10px] font-normal">
                {count[value]}
              </b>
            </button>
          ))}
        </div>
      ) : null}

      {shown.length ? (
        <ul className="-mx-1.5 flex min-h-0 flex-1 flex-col gap-0.5 px-1.5 lg:overflow-y-auto">
          {shown.map((row, index) => {
            const previous = shown[index - 1];
            const label = row.today ? "Today" : "Earlier";
            const showLabel = !previous || previous.today !== row.today;
            return (
              <Fragment key={row.key}>
                {showLabel ? (
                  <li
                    aria-hidden
                    className="text-on-dark-3 after:bg-pane-line flex items-center gap-2.5 px-2 pt-3 pb-1 font-mono text-[11px] tracking-[0.08em] uppercase after:h-px after:flex-1 after:content-['']"
                  >
                    {label}
                  </li>
                ) : null}
                <InboxRow
                  row={row}
                  selected={row.key === selectedKey}
                  onAnswered={() => setAnswered((keys) => [...keys, row.key])}
                />
              </Fragment>
            );
          })}
        </ul>
      ) : (
        <div className="text-on-dark-2 grid justify-items-center gap-3 px-2 py-6 text-center text-[13.5px]">
          <Image
            src={empty.image}
            alt=""
            width={260}
            height={195}
            unoptimized
            className="h-auto w-full max-w-[260px] rounded-xl"
          />
          <b className="font-display text-on-dark text-[17px] leading-tight font-bold tracking-[-0.02em]">
            {empty.title}
          </b>
          <span>{empty.text}</span>
          {empty.start ? (
            <Link
              href="#new-request"
              className="bg-mint text-pane inline-flex min-h-11 items-center rounded-[10px] px-4 text-[14px] font-semibold pointer-fine:min-h-10"
            >
              Write a request
            </Link>
          ) : null}
        </div>
      )}

      <div className="border-pane-line text-on-dark-3 flex justify-between border-t pt-3 font-mono text-[11px] tracking-[0.08em] uppercase">
        <span>Newest first</span>
        <span>
          {shown.length} of {rows.length}
        </span>
      </div>
    </div>
  );
}
