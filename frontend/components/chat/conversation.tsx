"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { ReportButton } from "@/components/safety/report-button";
import { SafetyTips } from "@/components/safety/safety-tips";
import { Button } from "@/components/ds/button";
import { Textarea } from "@/components/ds/fields";
import { cx } from "@/components/ui/cx";
import { browserApi } from "@/lib/api/browser";
import { ApiError } from "@/lib/api/errors";
import {
  messageSchema,
  messageUpdatesSchema,
  noContentSchema,
  type Message,
} from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { delayAfterError, nextPollDelay } from "@/lib/chat/cadence";

// The column's cap (MESSAGE_MAX_LENGTH); admins may set a lower limit (A6), which the API
// also enforces.
const MESSAGE_MAX_LENGTH = 2000;
// Safety tips show at the start of a conversation, until it has this many messages.
const FIRST_CHAT_MESSAGES = 10;

type ConversationProps = {
  connectionId: string;
  meId: string;
  otherId: string;
  otherName: string;
  /** Newest first, as the API returns them. */
  initial: Message[];
  /** Polling cursor taken before `initial` was loaded. */
  cursor: string;
  retentionDays: number;
  hasUnread: boolean;
  /** The message length limit from /api/v1/features (A6). */
  maxLength?: number;
};

/**
 * One conversation. New messages arrive by polling (ADR 0012): every 3 s after a message,
 * slower as it goes quiet, never while the tab is hidden, and not at all after 10 quiet
 * minutes until the person comes back, types or taps "Check for messages".
 */
export function Conversation({
  connectionId,
  meId,
  otherId,
  otherName,
  initial,
  cursor,
  retentionDays,
  hasUnread,
  maxLength = MESSAGE_MAX_LENGTH,
}: ConversationProps) {
  const [messages, setMessages] = useState<Message[]>(() => [...initial].reverse());
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
  const endRef = useRef<HTMLLIElement>(null);

  const markRead = useCallback(() => {
    browserApi(`/connections/${connectionId}/read`, noContentSchema, { method: "POST" }).catch(
      () => {
        // Unread counts catch up on the next visit.
      },
    );
  }, [connectionId]);

  /** Add messages not seen yet; returns how many were new. */
  const merge = useCallback((incoming: Message[]) => {
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
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length]);

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
        const fresh = merge(update.items.filter((m) => m.connection_id === connectionId));
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
  }, [connectionId, meId, merge, markRead, wakeups]);

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
      const message = await browserApi(`/connections/${connectionId}/messages`, messageSchema, {
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
            return (
              <li
                key={message.id}
                className={cx("flex flex-col gap-1", mine ? "items-end" : "items-start")}
              >
                <p
                  className={cx(
                    "rounded-panel max-w-[85%] px-3.5 py-2.5 break-words whitespace-pre-wrap lg:max-w-[70%]",
                    mine ? "bg-ink text-bg" : "border-line bg-panel text-ink border",
                  )}
                >
                  <span className="sr-only">{mine ? "You: " : `${otherName}: `}</span>
                  {message.body}
                </p>
                <div className="flex flex-wrap items-center gap-3">
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
                  {mine ? null : (
                    <ReportButton
                      kind="message"
                      targetId={message.id}
                      blockUserId={otherId}
                      blockName={otherName}
                      compact
                    />
                  )}
                </div>
              </li>
            );
          })}
          <li ref={endRef} aria-hidden className="h-0" />
        </ol>
      ) : (
        <p className="text-muted text-center">No messages yet. Say hello.</p>
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
          label={`Message ${otherName}`}
          hideLabel
          rows={2}
          maxLength={maxLength}
          showCounter={false}
          value={body}
          onChange={(event) => {
            setBody(event.target.value);
            wake();
          }}
          placeholder={`Message ${otherName}`}
          error={error}
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-meta text-muted">
            Messages are deleted {retentionDays} days after they&apos;re sent.
          </p>
          <Button type="submit" variant="primary" disabled={sending || !body.trim()}>
            {sending ? "Sending…" : "Send"}
          </Button>
        </div>
      </form>
    </div>
  );
}
