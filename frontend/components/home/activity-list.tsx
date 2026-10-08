"use client";

import { useState } from "react";

import { Avatar } from "@/components/ds/avatar";
import { ListRow, RowTile } from "@/components/ds/list-row";
import { SegmentedControl } from "@/components/ds/segmented-control";
import { StatusBadge } from "@/components/ds/surfaces";
import { itemHref, type ActivityRow, type Filter } from "@/lib/home/activity";

/** What an empty list says, per filter. The Messages wording is the old Messages page's. */
const EMPTY: Record<Filter, string> = {
  all: "No requests yet. Describe what you're building and we'll find people.",
  requests: "No requests yet. Describe what you're building and we'll find people.",
  messages:
    "No connections yet. When someone accepts your intro (or you accept theirs), they'll appear here.",
};

function leadingFor(row: ActivityRow) {
  if (row.type === "chat" && row.person) {
    return <Avatar userId={row.person.userId} name={row.person.name} decorative />;
  }
  return <RowTile kind={row.type === "intro" ? "intro" : "request"} />;
}

/**
 * The inbox list: the All / Requests / Messages filter over one list, newest first. The
 * pane around it gives the "Inbox" heading. Filtering happens here, without a reload; the
 * open item stays selected.
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
  const requestCount = rows.filter((row) => row.group === "requests").length;
  const messageCount = rows.filter((row) => row.group === "messages").length;
  const shown = filter === "all" ? rows : rows.filter((row) => row.group === filter);

  return (
    <div className="flex flex-col gap-2">
      <SegmentedControl
        label="Filter"
        value={filter}
        onChange={setFilter}
        segments={[
          { value: "all", label: "All" },
          { value: "requests", label: "Requests", count: requestCount },
          { value: "messages", label: "Messages", count: messageCount },
        ]}
      />
      {shown.length ? (
        <ul className="border-line mt-1 border-t">
          {shown.map((row) => (
            <ListRow
              key={row.key}
              href={itemHref(row.type, row.id)}
              leading={leadingFor(row)}
              title={row.title}
              secondary={row.secondary}
              time={row.time}
              badge={
                row.type === "request" ? (
                  <StatusBadge kind="request" />
                ) : row.type === "intro" ? (
                  <StatusBadge kind="intro" />
                ) : undefined
              }
              unread={row.unread}
              unreadLabel="Unread messages"
              selected={row.key === selectedKey}
            />
          ))}
        </ul>
      ) : (
        <p className="text-muted py-4">{EMPTY[filter]}</p>
      )}
    </div>
  );
}
