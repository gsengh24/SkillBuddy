"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ds/button";
import { InlineError } from "@/components/ds/fields";
import { ClockIcon, PeopleIcon, PlusIcon } from "@/components/ds/icons";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema, profileSchema, type Nudge } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

/** The words for each kind the API may send; an unknown kind is not shown. */
function wordsFor(nudge: Nudge): { label: string; text: string; action: string } | null {
  if (nudge.kind === "team_skill" && nudge.skill) {
    return {
      label: "Suggestion",
      text: `You joined ${nudge.team_name ?? "a team"}. Add ${nudge.skill} to your skills?`,
      action: "Add",
    };
  }
  if (nudge.kind === "availability") {
    return {
      label: "After your first match",
      text: "Add your availability so people know when you're free.",
      action: "Add availability",
    };
  }
  return null;
}

/**
 * One small suggestion at the top of the inbox, after an event (ADR 0022, screen 11). Add
 * acts in one tap; Dismiss and ✕ hide it for good. The API decides which nudge and when
 * (at most one a day, each kind once).
 */
export function NudgeCard({ nudge, offerSkills }: { nudge: Nudge; offerSkills: string[] }) {
  const router = useRouter();
  const [state, setState] = useState<"shown" | "busy" | "done" | "gone">("shown");
  const [error, setError] = useState<string | null>(null);
  const words = wordsFor(nudge);
  if (!words || state === "gone") return null;
  if (state === "done") {
    return (
      <p role="status" className="text-on-dark-2 text-[13px]">
        Added {nudge.skill} to your skills.
      </p>
    );
  }

  async function dismiss() {
    await browserApi(`/me/nudges/${nudge.kind}/dismiss`, noContentSchema, { method: "POST" });
  }

  async function act() {
    setState("busy");
    setError(null);
    try {
      if (nudge.kind === "availability") {
        await dismiss();
        router.push("/you#s-avail");
        return;
      }
      await browserApi("/me/profile", profileSchema, {
        method: "PATCH",
        body: { offer_skills: [...offerSkills, nudge.skill] },
      });
      await dismiss();
      setState("done");
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
      setState("shown");
    }
  }

  async function close() {
    setState("gone");
    try {
      await dismiss();
    } catch {
      // Not saved: it may show again today, and never after today.
    }
  }

  const busy = state === "busy";
  return (
    <section
      aria-label="Suggestion"
      className="bg-card border-line text-ink grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 rounded-[14px] border p-3.5"
    >
      <span className="bg-green-tint text-green grid size-9 place-items-center rounded-full">
        {nudge.kind === "availability" ? (
          <ClockIcon className="size-[18px]" />
        ) : (
          <PeopleIcon className="size-[18px]" />
        )}
      </span>
      <div className="min-w-0">
        <p className="text-mono text-green font-mono uppercase">{words.label}</p>
        <p className="text-meta-lg mt-1">{words.text}</p>
        <div className="mt-2.5 flex flex-wrap gap-2">
          <Button variant="outline" size="compact" disabled={busy} onClick={act}>
            <PlusIcon className="size-4" />
            {words.action}
          </Button>
          <Button variant="ghost" size="compact" disabled={busy} onClick={close}>
            Dismiss
          </Button>
        </div>
        {error ? <InlineError announce>{error}</InlineError> : null}
      </div>
      <button
        type="button"
        onClick={close}
        disabled={busy}
        aria-label="Dismiss suggestion"
        className="text-ink-2 hover:text-ink -m-2 grid size-11 place-items-center text-[18px] leading-none"
      >
        <span aria-hidden>×</span>
      </button>
    </section>
  );
}
