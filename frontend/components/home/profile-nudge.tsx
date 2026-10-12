"use client";

import { useEffect, useId, useRef, useState } from "react";

import { ButtonLink } from "@/components/ds/button";
import { cx } from "@/components/ui/cx";
import { TextLink } from "@/components/ui/text-link";
import {
  NUDGE_DISMISSED_KEY,
  shouldShowProfileNudge,
  type NudgeStrength,
} from "@/lib/profile/nudge";

const SHOW_AFTER_MS = 1200;
const LEAVE_MS = 250;
const RING = { size: 44, stroke: 3, radius: 19 };
const CIRCUMFERENCE = 2 * Math.PI * RING.radius;

/** Closed or shown already in this page load: the popup appears at most once per load. */
let shownThisLoad = false;

/** For tests only: a fresh page load. */
export function resetProfileNudgeForTests() {
  shownThisLoad = false;
}

function readDismissed(): string | null {
  try {
    return window.localStorage.getItem(NUDGE_DISMISSED_KEY);
  } catch {
    return null;
  }
}

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

type Phase = "idle" | "entering" | "shown" | "leaving";

/**
 * "Finish your profile", a small card on Home for people signing in again with an incomplete
 * profile. Closing it hides it until the next sign-in. It does not take focus and is not a
 * modal. The rule for showing it is `shouldShowProfileNudge`; this only renders and animates
 * (transform and opacity, once).
 */
export function ProfileNudge({
  user,
  strength,
}: {
  user: { created_at: string; session_started_at?: string };
  strength: NudgeStrength | null;
}) {
  const titleId = useId();
  const [phase, setPhase] = useState<Phase>("idle");
  const [reduced, setReduced] = useState(false);
  const card = useRef<HTMLElement>(null);
  const cameFrom = useRef<Element | null>(null);
  const startedAt = user.session_started_at;
  // The rule without the stored dismissal, which only the browser can read (in the effect).
  const eligible = shouldShowProfileNudge({ user, strength, dismissedFor: null });

  useEffect(() => {
    if (shownThisLoad || !eligible || readDismissed() === startedAt) return;
    const motionOff = prefersReducedMotion();
    let frame = 0;
    const timer = window.setTimeout(
      () => {
        shownThisLoad = true;
        setReduced(motionOff);
        setPhase("entering");
        frame = window.requestAnimationFrame(() => setPhase("shown"));
      },
      motionOff ? 0 : SHOW_AFTER_MS,
    );
    return () => {
      window.clearTimeout(timer);
      window.cancelAnimationFrame(frame);
    };
  }, [eligible, startedAt]);

  useEffect(() => {
    if (phase !== "leaving") return;
    const timer = window.setTimeout(() => setPhase("idle"), reduced ? 0 : LEAVE_MS);
    return () => window.clearTimeout(timer);
  }, [phase, reduced]);

  if (!strength || strength.missing.length === 0 || phase === "idle") return null;
  const { done, total, missing } = strength;
  const first = missing[0];
  if (!first) return null;

  function close() {
    try {
      if (startedAt) window.localStorage.setItem(NUDGE_DISMISSED_KEY, startedAt);
    } catch {
      // Private browsing: it simply shows again.
    }
    const hadFocus = card.current?.contains(document.activeElement) ?? false;
    setPhase("leaving");
    if (hadFocus) {
      const back = cameFrom.current;
      const target =
        back instanceof HTMLElement && back.isConnected && !card.current?.contains(back)
          ? back
          : document.querySelector<HTMLElement>('a[aria-label^="Notifications"]');
      target?.focus();
    }
  }

  const visible = phase === "shown";
  return (
    <aside
      ref={card}
      aria-labelledby={titleId}
      onFocus={(event) => {
        if (!card.current?.contains(event.relatedTarget as Node | null)) {
          cameFrom.current = event.relatedTarget as Element | null;
        }
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") close();
      }}
      className={cx(
        "bg-card border-line fixed inset-x-3 top-[68px] z-30 grid grid-cols-[44px_minmax(0,1fr)_auto] items-start gap-3 rounded-[16px] border p-3.5 shadow-[0_8px_24px_rgb(0_0_0/0.25)]",
        "lg:inset-x-auto lg:top-[76px] lg:right-6 lg:w-80",
        !reduced && "origin-top-right",
        !reduced &&
          (phase === "leaving"
            ? "transition-[opacity,transform] duration-250 ease-out"
            : "transition-[opacity,transform] duration-[550ms] ease-[cubic-bezier(.2,.9,.25,1.15)]"),
        visible ? "opacity-100" : "opacity-0",
        !reduced &&
          !visible &&
          (phase === "leaving"
            ? "-translate-y-2 scale-[.96]"
            : "translate-x-[18px] -translate-y-1.5 scale-[.97]"),
      )}
    >
      <div
        className="text-ink relative grid size-11 place-items-center font-mono text-[11px]"
        role="img"
        aria-label={`${done} of ${total} done`}
      >
        <svg aria-hidden viewBox="0 0 44 44" className="absolute inset-0 size-11 -rotate-90">
          <circle
            cx="22"
            cy="22"
            r={RING.radius}
            fill="none"
            strokeWidth={RING.stroke}
            className="stroke-line-strong"
          />
          <circle
            cx="22"
            cy="22"
            r={RING.radius}
            fill="none"
            strokeWidth={RING.stroke}
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={CIRCUMFERENCE * (1 - done / total)}
            className="stroke-green"
          />
        </svg>
        <span aria-hidden>
          {done}/{total}
        </span>
      </div>

      <div className="min-w-0">
        <h2
          id={titleId}
          className="text-ink font-display text-[15px] leading-tight font-bold tracking-[-0.01em]"
        >
          Finish your profile
        </h2>
        <p className="text-ink-2 mt-1 text-[13px] leading-snug">
          {done} of {total} done. Fuller profiles get better matches.
        </p>
        <ul className="mt-2 flex flex-col items-start gap-1 text-[13px]">
          {missing.slice(0, 2).map((item) => (
            <li key={item.label}>
              <TextLink href={`/you${item.href}`} prefetch={false} tone="green">
                {item.label}
              </TextLink>
            </li>
          ))}
        </ul>
        <ButtonLink
          href={`/you${first.href}`}
          prefetch={false}
          variant="primary"
          size="compact"
          className="mt-3"
        >
          Finish profile →
        </ButtonLink>
      </div>

      <button
        type="button"
        onClick={close}
        aria-label="Dismiss until next sign-in"
        className="text-ink-2 hover:text-ink -m-2 grid size-11 place-items-center"
      >
        <span
          aria-hidden
          className="border-line grid size-7 place-items-center rounded-full border text-[16px] leading-none"
        >
          ×
        </span>
      </button>
    </aside>
  );
}
