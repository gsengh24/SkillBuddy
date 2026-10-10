"use client";

import { useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { IntentChip } from "@/components/ui/intent-chip";
import { browserApi } from "@/lib/api/browser";
import {
  matchListSchema,
  matchRequestSchema,
  type Match,
  type MatchRequest,
} from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

import { MatchCard } from "./match-card";

const POLL_MS = 3000;
const MAX_POLLS = 40;

/**
 * One request and its matches, under the matcher's heading for it (the person's own
 * words are a small line below). While the request is pending it polls until the matches
 * are ready (usually seconds; the first request after an idle period can take a minute).
 */
export function RequestCard({ initial }: { initial: MatchRequest }) {
  const ids = useId();
  const [request, setRequest] = useState(initial);
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [polls, setPolls] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);

  const pending = request.status === "pending";
  const gaveUp = pending && polls >= MAX_POLLS;

  useEffect(() => {
    if (!pending || gaveUp) return;
    const timer = window.setTimeout(async () => {
      try {
        setRequest(await browserApi(`/requests/${request.id}`, matchRequestSchema));
      } catch {
        // Retried on the next tick.
      }
      setPolls((count) => count + 1);
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [pending, gaveUp, polls, request.id]);

  useEffect(() => {
    if (pending || matches !== null) return;
    let cancelled = false;
    browserApi(`/requests/${request.id}/matches`, matchListSchema)
      .then((list) => {
        if (!cancelled) setMatches(list.items);
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(describeError(caught));
      });
    return () => {
      cancelled = true;
    };
  }, [pending, matches, request.id]);

  async function close() {
    setClosing(true);
    setError(null);
    try {
      setRequest(
        await browserApi(`/requests/${request.id}/close`, matchRequestSchema, { method: "POST" }),
      );
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setClosing(false);
    }
  }

  const intent = request.intent ?? request.requested_intent;
  const open = request.status === "pending" || request.status === "ready";

  return (
    <section aria-labelledby={`${ids}-h`} className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {intent ? <IntentChip intent={intent} /> : null}
          {!open ? (
            <span className="text-small text-muted">
              {request.status === "closed" ? "Closed" : "Expired"}
            </span>
          ) : null}
        </div>
        <h3 id={`${ids}-h`} className="text-title lg:text-title-lg text-ink">
          {request.title?.trim() || "Your request"}
        </h3>
        {/* Their own words stay, but small: the heading is the platform's. */}
        <p className="text-meta-lg text-muted">
          You asked: <span>“{request.text}”</span>
        </p>
      </div>

      <p role="status" aria-live="polite" className={pending ? "text-muted" : "sr-only"}>
        {pending && !gaveUp ? "Finding people for this…" : null}
        {gaveUp ? "This is taking longer than usual. Check back in a few minutes." : null}
        {!pending && matches !== null
          ? `${matches.length} ${matches.length === 1 ? "match" : "matches"} ready.`
          : null}
      </p>

      {error ? (
        <p role="alert" className="text-small text-coral-ink font-semibold">
          {error}
        </p>
      ) : null}

      {!pending && matches !== null && matches.length === 0 ? (
        <p className="text-muted">
          Nobody fits yet. We keep looking as people join, so check back soon.
        </p>
      ) : null}

      {matches && matches.length ? (
        <ul className="grid gap-4 md:grid-cols-2">
          {matches.map((match) => (
            <li key={match.id}>
              <MatchCard match={match} teamId={request.team_id} />
            </li>
          ))}
        </ul>
      ) : null}

      {open ? (
        <Button type="button" onClick={close} disabled={closing} className="self-start">
          {closing ? "Closing…" : "Close this request"}
        </Button>
      ) : null}
    </section>
  );
}
