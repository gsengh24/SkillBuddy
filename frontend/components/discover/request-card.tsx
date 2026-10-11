"use client";

import Image from "next/image";
import { useEffect, useId, useState, type ReactNode } from "react";

import { Button } from "@/components/ds/button";
import { browserApi } from "@/lib/api/browser";
import {
  matchListSchema,
  matchRequestSchema,
  type Match,
  type MatchRequest,
} from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { intents } from "@/lib/design/tokens";
import { agoLabel } from "@/lib/home/activity";
import { notifyHomeChanged } from "@/lib/home/changed";

import { MatchCard } from "./match-card";

const POLL_MS = 3000;
const MAX_POLLS = 40;

/**
 * One request and its matches, under the matcher's heading for it (the person's own
 * words are a small line below). While the request is pending it polls until the matches
 * are ready (usually seconds; the first request after an idle period can take a minute).
 *
 * `initialMatches` are the matches the page already loaded. They are used only for a request
 * that is not pending: a pending one has none yet, so it fetches them when it becomes ready.
 */
export function RequestCard({
  initial,
  initialMatches,
}: {
  initial: MatchRequest;
  initialMatches?: Match[];
}) {
  const ids = useId();
  const [request, setRequest] = useState(initial);
  const [matches, setMatches] = useState<Match[] | null>(
    initial.status === "pending" ? null : (initialMatches ?? null),
  );
  const [polls, setPolls] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);

  const pending = request.status === "pending";
  const gaveUp = pending && polls >= MAX_POLLS;

  useEffect(() => {
    if (!pending || gaveUp) return;
    const timer = window.setTimeout(async () => {
      try {
        const next = await browserApi(`/requests/${request.id}`, matchRequestSchema);
        setRequest(next);
        // Its row in the inbox still says "Finding people…".
        if (next.status !== "pending") notifyHomeChanged();
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
      notifyHomeChanged();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setClosing(false);
    }
  }

  const intent = request.intent ?? request.requested_intent;
  const open = request.status === "pending" || request.status === "ready";
  const nobody = !pending && matches !== null && matches.length === 0;

  return (
    <section aria-labelledby={`${ids}-h`} className="flex flex-col">
      <p className="text-green font-mono text-[11px] leading-[1.4] font-medium tracking-[0.08em] uppercase">
        Your request
        <span suppressHydrationWarning>
          {" · "}
          {agoLabel(request.created_at, new Date()).toUpperCase()}
        </span>
        {!open ? (
          <>
            {" · "}
            <span>{request.status === "closed" ? "Closed" : "Expired"}</span>
          </>
        ) : null}
      </p>
      <h2
        id={`${ids}-h`}
        className="font-display mt-1.5 mb-1 text-[26px] leading-[1.05] font-extrabold tracking-[-0.03em] text-balance lg:text-[30px]"
      >
        {request.title?.trim() || "Your request"}
      </h2>
      {/* Their own words stay, but small: the heading is the platform's. */}
      <p className="text-meta-lg text-muted mb-3">
        You asked: <span>“{request.text}”</span>
      </p>
      {intent ? (
        <p className="mb-[22px]">
          <span className="bg-green-tint text-green inline-flex items-center gap-1.5 rounded-full px-2.5 py-[5px] text-[12.5px] font-medium">
            <span aria-hidden className="bg-green size-1.5 rounded-full" />
            {intents[intent].label}
          </span>
        </p>
      ) : null}

      <p role="status" aria-live="polite" className="sr-only">
        {pending && !gaveUp ? "Finding people for this…" : null}
        {gaveUp ? "This is taking longer than usual. Check back in a few minutes." : null}
        {!pending && matches !== null
          ? `${matches.length} ${matches.length === 1 ? "match" : "matches"} ready.`
          : null}
      </p>

      {error ? (
        <p role="alert" className="text-small text-coral-ink mb-3 font-semibold">
          {error}
        </p>
      ) : null}

      {pending ? (
        <StateBlock
          image="/art/home/home_finding.jpg"
          alt="A ring of light around a few spheres picked out from a wider field."
          label="Finding matches"
          title={gaveUp ? "This is taking longer than usual." : "We're reading through people now."}
          scanning={!gaveUp}
        >
          {gaveUp
            ? "Check back in a few minutes. We'll tell you when your matches are ready."
            : "This usually takes a minute or two. We'll tell you when your matches are ready, with a reason for each one."}
        </StateBlock>
      ) : null}

      {nobody ? (
        <StateBlock
          image="/art/home/home_nobody_fits.jpg"
          alt="One green sphere on a pedestal beside three empty pedestals."
          label="No matches"
          title="Nobody fits yet."
        >
          We&apos;d rather show you no one than the wrong people. We keep looking as people join, so
          check back soon, or try saying more about what you want to talk about.
        </StateBlock>
      ) : null}

      {matches && matches.length ? (
        <>
          <p className="text-ink-2 mb-[22px]">
            {matches.length} {matches.length === 1 ? "person" : "people"}, each with a reason.
            You&apos;ll see their name only if they accept your intro.
          </p>
          <ul className="grid gap-3">
            {matches.map((match) => (
              <li key={match.id}>
                <MatchCard match={match} teamId={request.team_id} />
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {open ? (
        <Button
          type="button"
          variant="ghost"
          onClick={close}
          disabled={closing}
          className="border-line-strong! mt-5 self-start rounded-[10px]"
        >
          {closing ? "Closing…" : "Close this request"}
        </Button>
      ) : null}
    </section>
  );
}

/** A dashed panel for a request that is still being matched, or has no matches. */
function StateBlock({
  image,
  alt,
  label,
  title,
  scanning = false,
  children,
}: {
  image: string;
  alt: string;
  label: string;
  title: string;
  scanning?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="border-line-strong grid justify-items-start gap-3 rounded-[14px] border border-dashed px-[22px] py-7">
      <Image
        src={image}
        alt={alt}
        width={360}
        height={270}
        unoptimized
        className="aspect-[4/3] h-auto w-full max-w-[360px] rounded-xl object-cover"
      />
      <span className="text-green font-mono text-[11px] leading-[1.4] font-medium tracking-[0.08em] uppercase">
        {label}
      </span>
      <h3 className="font-display text-[24px] leading-[1.1] font-extrabold tracking-[-0.03em]">
        {title}
      </h3>
      <p className="text-ink-2 max-w-[52ch]">{children}</p>
      {scanning ? (
        <div aria-hidden className="bg-line h-[3px] w-full overflow-hidden rounded-[3px]">
          <i className="bg-green animate-scan block h-full w-2/5 rounded-[3px]" />
        </div>
      ) : null}
    </div>
  );
}
