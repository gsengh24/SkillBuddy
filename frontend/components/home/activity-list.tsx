"use client";

import { useState } from "react";

import { Avatar } from "@/components/ds/avatar";
import { ListRow, RowTile } from "@/components/ds/list-row";
import { SegmentedControl } from "@/components/ds/segmented-control";
import { StatusBadge } from "@/components/ds/surfaces";
import { itemHref, type ActivityRow, type Filter } from "@/lib/home/activity";

/** What an empty list says, per filter. The Messages wording is the old Messages page's. */
const EMPTY: Record<Filter, string> = {
  all: "Nothing here yet. Your requests, intros and chats will show up here.",
  requests: "No requests yet. Ask for the kind of person you want to meet above.",
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
 * "Recent activity": the All / Requests / Messages filter over one list, newest first.
 * Filtering happens here, without a reload; the open item stays selected.
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
    <section aria-labelledby="activity-h" className="flex flex-col gap-2">
      <h2 id="activity-h" className="text-mono text-muted mt-5 font-mono uppercase">
        Recent activity
      </h2>
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
    </section>
  );
}
