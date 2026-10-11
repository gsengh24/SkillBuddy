"use client";

import { Fragment, useCallback, useEffect, useRef, useState, type FormEvent } from "react";

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

/** "Today", "Yesterday", or a short date: the label over the first message of a day. */
function dayLabel(iso: string | undefined): string {
  if (!iso) return "";
  const then = new Date(iso);
  const midnight = (date: Date) =>
    new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const days = Math.round((midnight(new Date()) - midnight(then)) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return then.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

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
  const listRef = useRef<HTMLOListElement>(null);

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
    // Keep the newest message in view by scrolling the list itself, never the page.
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
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
        // The list scrolls on its own, so a long chat never makes the page longer. It can
        // take focus, so it also scrolls from the keyboard.
        <ol
          ref={listRef}
          aria-label="Messages"
          tabIndex={0}
          className="-mx-1 flex max-h-[60dvh] flex-col gap-3 overflow-y-auto overscroll-contain px-1 py-1 pr-2"
        >
          {messages.map((message, index) => {
            const mine = message.sender_id === meId;
            const day = dayLabel(message.created_at);
            const newDay = day !== dayLabel(messages[index - 1]?.created_at);
            return (
              <Fragment key={message.id}>
                {newDay ? (
                  <li
                    aria-hidden
                    suppressHydrationWarning
                    className="text-muted self-center py-1.5 font-mono text-[11px] tracking-[0.08em] uppercase"
                  >
                    {day}
                  </li>
                ) : null}
                <li className={cx("flex flex-col gap-1", mine ? "items-end" : "items-start")}>
                  <p
                    className={cx(
                      "max-w-[85%] rounded-[14px] px-3.5 py-2.5 text-[15px] break-words whitespace-pre-wrap lg:max-w-[78%]",
                      mine
                        ? "bg-ink text-bg rounded-br-[4px]"
                        : "bg-panel text-ink rounded-bl-[4px]",
                    )}
                  >
                    <span className="sr-only">{mine ? "You: " : `${otherName}: `}</span>
                    {message.body}
                    <time
                      dateTime={message.created_at}
                      suppressHydrationWarning
                      title={new Date(message.created_at).toLocaleString(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                      className="mt-1 block font-mono text-[10.5px] opacity-60"
                    >
                      {new Date(message.created_at).toLocaleTimeString(undefined, {
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: false,
                      })}
                    </time>
                  </p>
                  <div className="flex flex-wrap items-center gap-3">
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
              </Fragment>
            );
          })}
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

      <form onSubmit={send} className="flex flex-col gap-2">
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <Textarea
              label={`Message ${otherName}`}
              hideLabel
              rows={1}
              maxLength={maxLength}
              showCounter={false}
              value={body}
              onChange={(event) => {
                setBody(event.target.value);
                wake();
              }}
              placeholder="Write a message"
              error={error}
              className="bg-card min-h-12! resize-none rounded-xl px-3.5 py-3 text-[16px]"
            />
          </div>
          <Button
            type="submit"
            variant="primary"
            disabled={sending || !body.trim()}
            className="min-h-12 rounded-xl px-[22px] text-[15px] font-semibold"
          >
            {sending ? "Sending…" : "Send"}
          </Button>
        </div>
        <p className="text-meta text-muted">
          Messages are deleted {retentionDays} days after they&apos;re sent.
        </p>
      </form>
    </div>
  );
}
