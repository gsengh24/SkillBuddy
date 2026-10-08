"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { TextLink } from "@/components/ui/text-link";
import { browserApi } from "@/lib/api/browser";
import { markedReadSchema, type AppNotification } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { CONTENT_RULES } from "@/lib/content-rules";

const WORDS: Record<AppNotification["kind"], { text: string; href: string; link: string }> = {
  intro_received: {
    text: "Someone sent you an intro.",
    href: "/notifications#intros",
    link: "See intros",
  },
  intro_accepted: {
    text: "Your intro was accepted. You're now connected.",
    href: "/home?filter=messages",
    link: "Open Messages",
  },
  matches_ready: { text: "Your matches are ready.", href: "/home", link: "Open Discover" },
  report_reviewed: {
    text: "We reviewed your report. Thank you for helping keep the community safe.",
    href: "/notifications",
    link: "OK",
  },
  content_removed: {
    text: "We removed some text you wrote because it broke our rules.",
    href: "/terms",
    link: "Read the terms",
  },
};

/** "Reason: contact details." for a content_removed notice (A7). */
function ruleReason(item: AppNotification): string | null {
  const rule = item.kind === "content_removed" && item.rule ? CONTENT_RULES[item.rule] : undefined;
  return rule ? ` Reason: ${rule.reason}.` : null;
}

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

/** The notification list, with "Mark all as read". */
export function NotificationList({
  initial,
  unread,
}: {
  initial: AppNotification[];
  unread: number;
}) {
  const [items, setItems] = useState(initial);
  const [count, setCount] = useState(unread);
  const [error, setError] = useState<string | null>(null);

  async function markAll() {
    setError(null);
    try {
      await browserApi("/notifications/read", markedReadSchema, { method: "POST", body: {} });
      const now = new Date().toISOString();
      setItems((current) => current.map((item) => ({ ...item, read_at: item.read_at ?? now })));
      setCount(0);
    } catch (caught) {
      setError(describeError(caught));
    }
  }

  if (!items.length) return <p className="text-muted">Nothing yet.</p>;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-small text-muted" role="status">
          {count ? `${count} unread` : "All read"}
        </p>
        {count ? (
          <Button type="button" onClick={markAll}>
            Mark all as read
          </Button>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="text-small text-coral-ink font-semibold">
          {error}
        </p>
      ) : null}
      <ul className="border-line divide-line flex flex-col divide-y border-y">
        {items.map((item) => {
          const words = WORDS[item.kind];
          return (
            <li key={item.id} className="flex flex-col gap-1 py-3">
              <p className={item.read_at ? "text-ink" : "text-ink font-bold"}>
                {item.read_at ? null : <span className="sr-only">Unread: </span>}
                {words.text}
                {ruleReason(item)}
              </p>
              <p className="text-small text-muted flex flex-wrap gap-3">
                <span>{when(item.created_at)}</span>
                <TextLink href={words.href}>{words.link}</TextLink>
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
