"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { Textarea } from "@/components/ds/fields";
import { SafetyTips } from "@/components/safety/safety-tips";
import { cx } from "@/components/ui/cx";
import { browserApi } from "@/lib/api/browser";
import { ApiError } from "@/lib/api/errors";
import {
  messageUpdatesSchema,
  noContentSchema,
  teamMessageSchema,
  type TeamMessage,
} from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { delayAfterError, nextPollDelay } from "@/lib/chat/cadence";

// The column's cap (MESSAGE_MAX_LENGTH); admins may set a lower limit (A6), which the API
// also enforces.
const MESSAGE_MAX_LENGTH = 2000;
// Safety tips show at the start of a chat, until it has this many messages.
const FIRST_CHAT_MESSAGES = 10;

type TeamChatProps = {
  teamId: string;
  teamName: string;
  meId: string;
  /** Members' names by id; people who have left fall back to "A teammate". */
  names: Record<string, string>;
  /** Newest first, as the API returns them. */
  initial: TeamMessage[];
  /** Polling cursor taken before `initial` was loaded. */
  cursor: string;
  retentionDays: number;
  hasUnread: boolean;
  /** The message length limit from /api/v1/features (A6). */
  maxLength?: number;
};

/**
 * A team's chat (ADR 0016). New messages arrive through the same poll as one-to-one chat
 * (ADR 0012): every 3 s after a message, slower as it goes quiet, never while the tab is
 * hidden, and not at all after 10 quiet minutes until the person comes back or types.
 */
export function TeamChat({
  teamId,
  teamName,
  meId,
  names,
  initial,
  cursor,
  retentionDays,
  hasUnread,
  maxLength = MESSAGE_MAX_LENGTH,
}: TeamChatProps) {
  const [messages, setMessages] = useState<TeamMessage[]>(() => [...initial].reverse());
  const [paused, setPaused] = useState(false);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wakeups, setWakeups] = useState(0);

  const cursorRef = useRef(cursor);
  const seenRef = useRef(new Set(initial.map((message) => message.id)));
  // When the last message or sign of the person was; set on mount (0 until then).
  const activityRef = useRef(0);
  const stoppedRef = useRef(false);

  const markRead = useCallback(() => {
    browserApi(`/teams/${teamId}/read`, noContentSchema, { method: "POST" }).catch(() => {
      // Unread counts catch up on the next visit.
    });
  }, [teamId]);

  /** Add messages not seen yet; returns the new ones. */
  const merge = useCallback((incoming: TeamMessage[]) => {
    const fresh = incoming.filter((message) => !seenRef.current.has(message.id));
    for (const message of fresh) seenRef.current.add(message.id);
    if (fresh.length) setMessages((current) => [...current, ...fresh]);
    return fresh;
  }, []);

  /** The person is here: count it as activity and restart polling if it had stopped. */
  const wake = useCallback(() => {
    activityRef.current = Date.now();
    if (stoppedRef.current) {
      stoppedRef.current = false;
      setPaused(false);
      setWakeups((count) => count + 1);
    }
  }, []);

  useEffect(() => {
    if (hasUnread) markRead();
  }, [hasUnread, markRead]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    if (!activityRef.current) activityRef.current = Date.now();

    function schedule(delay: number | null) {
      if (cancelled) return;
      if (delay === null) {
        stoppedRef.current = true;
        setPaused(true);
        return;
      }
      timer = window.setTimeout(tick, delay);
    }

    async function tick() {
      if (document.visibilityState === "hidden") {
        stoppedRef.current = true;
        return;
      }
      try {
        const update = await browserApi(
          `/messages/updates?after=${encodeURIComponent(cursorRef.current)}`,
          messageUpdatesSchema,
        );
        if (cancelled) return;
        cursorRef.current = update.cursor;
        const fresh = merge(update.team_items.filter((message) => message.team_id === teamId));
        if (fresh.length) {
          activityRef.current = Date.now();
          if (fresh.some((message) => message.sender_id !== meId)) markRead();
        }
        if (update.has_more) return schedule(0);
        schedule(nextPollDelay(Date.now() - activityRef.current, update.poll_after_seconds));
      } catch (caught) {
        schedule(
          delayAfterError(caught instanceof ApiError ? caught.retryAfterSeconds : undefined),
        );
      }
    }

    // On a wake-up (back from away, typing) check right away; on first load, wait a beat.
    schedule(wakeups ? 0 : nextPollDelay(Date.now() - activityRef.current));
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [teamId, meId, merge, markRead, wakeups]);

  useEffect(() => {
    function onVisible() {
      if (document.visibilityState === "visible") wake();
    }
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", wake);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", wake);
    };
  }, [wake]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = body.trim();
    if (!text) return;
    setSending(true);
    setError(null);
    try {
      const message = await browserApi(`/teams/${teamId}/messages`, teamMessageSchema, {
        method: "POST",
        body: { body: text },
      });
      merge([message]);
      setBody("");
      wake();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {messages.length < FIRST_CHAT_MESSAGES ? <SafetyTips /> : null}
      {messages.length ? (
        <ol aria-label="Messages" className="flex flex-col gap-3">
          {messages.map((message) => {
            const mine = message.sender_id === meId;
            const sender = mine ? "You" : (names[message.sender_id] ?? "A teammate");
            return (
              <li
                key={message.id}
                className={cx("flex flex-col gap-1", mine ? "items-end" : "items-start")}
              >
                {mine ? null : <p className="text-meta text-muted">{sender}</p>}
                <p
                  className={cx(
                    "rounded-panel max-w-[85%] px-3.5 py-2.5 break-words whitespace-pre-wrap lg:max-w-[70%]",
                    mine ? "bg-ink text-bg" : "border-line bg-panel text-ink border",
                  )}
                >
                  {mine ? <span className="sr-only">You: </span> : null}
                  {message.body}
                </p>
                <time
                  dateTime={message.created_at}
                  suppressHydrationWarning
                  className="text-meta text-muted"
                >
                  {new Date(message.created_at).toLocaleString(undefined, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })}
                </time>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="text-muted">No messages yet. Say hello to the team.</p>
      )}

      {paused ? (
        <div role="status" className="flex flex-wrap items-center gap-3">
          <p className="text-meta-lg text-muted">
            Paused while it&apos;s quiet. New messages load when you come back.
          </p>
          <Button variant="outline" onClick={wake}>
            Check for messages
          </Button>
        </div>
      ) : null}

      <form onSubmit={send} className="border-line flex flex-col gap-3 border-t pt-4">
        <Textarea
          label={`Message ${teamName}`}
          hideLabel
          rows={2}
          maxLength={maxLength}
          showCounter={false}
          value={body}
          onChange={(event) => {
            setBody(event.target.value);
            wake();
          }}
          placeholder={`Message ${teamName}`}
          error={error}
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-meta text-muted">
            Everyone in the team can read this. Messages are deleted {retentionDays} days after
            they&apos;re sent.
          </p>
          <Button type="submit" variant="primary" disabled={sending || !body.trim()}>
            {sending ? "Sending…" : "Send"}
          </Button>
        </div>
      </form>
    </div>
  );
}
