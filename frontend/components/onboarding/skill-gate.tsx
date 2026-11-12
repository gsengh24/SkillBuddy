"use client";

import { useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ds/button";
import { ChoiceChip } from "@/components/ds/choices";
import { Dialog } from "@/components/ds/dialog";
import { InlineError } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { ApiError } from "@/lib/api/errors";
import { onboardingSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { MAX_TAGS, includesTag, toggleTag } from "@/lib/onboarding/catalog";

import { SkillSearch } from "./skill-search";

/** The API's rule (MIN_OFFERED_SKILLS): offered skills needed to send an intro or join. */
export const GATE_SKILLS = 3;
const SUGGESTED = [
  "Python",
  "React",
  "Figma",
  "UI design",
  "Node.js",
  "Flutter",
  "Machine learning",
  "Writing",
];

type Pending = { retry: () => Promise<unknown>; done: (value: unknown) => void };

/**
 * The soft gate (ADR 0022, screen 9): when the API answers an intro or a join with
 * `skills_required`, ask for three skills inline, save them, and carry on with the same
 * action. "Not now" leaves it undone. The server enforces the rule; this only helps.
 *
 * `guard(action)` returns the action's result, or undefined when the person chose "Not now".
 */
export function useSkillGate(): {
  guard: <T>(action: () => Promise<T>) => Promise<T | undefined>;
  dialog: ReactNode;
} {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<Pending | null>(null);
  // Where focus was (the Send or Join button): it goes back there once the dialog closes,
  // after the caller has enabled that button again.
  const returnTo = useRef<HTMLElement | null>(null);

  function close(result: unknown) {
    setOpen(false);
    pending.current?.done(result);
    pending.current = null;
    const target = returnTo.current;
    // The caller re-enables its button a render or two later; wait for it (a few frames).
    let frames = 10;
    const refocus = () => {
      if (!target?.isConnected) return;
      if (target.matches(":disabled") && frames-- > 0) {
        window.requestAnimationFrame(refocus);
        return;
      }
      target.focus();
    };
    window.requestAnimationFrame(refocus);
  }

  async function guard<T>(action: () => Promise<T>): Promise<T | undefined> {
    // Remember the button now: once the action starts the caller disables it, and a
    // disabled button loses focus.
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    try {
      return await action();
    } catch (caught) {
      if (!(caught instanceof ApiError && caught.code === "skills_required")) throw caught;
    }
    // Start from what the person already offers.
    try {
      const progress = await browserApi("/me/onboarding", onboardingSchema);
      setPicked(progress.offer_skills);
    } catch {
      setPicked([]);
    }
    setError(null);
    returnTo.current = opener;
    setOpen(true);
    return new Promise<T | undefined>((resolve) => {
      pending.current = { retry: action, done: (value) => resolve(value as T | undefined) };
    });
  }

  function notNow() {
    close(undefined);
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await browserApi("/me/onboarding/offers", onboardingSchema, {
        method: "PUT",
        body: { skills: picked },
      });
      close(await pending.current?.retry());
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  const choices = [...picked.filter((skill) => !includesTag(SUGGESTED, skill)), ...SUGGESTED];
  const enough = picked.length >= GATE_SKILLS;

  const dialog = (
    <Dialog
      open={open}
      onClose={notNow}
      title="Add 3 skills first"
      description={
        <>
          <span className="text-mono-lg text-green mb-1 block font-mono uppercase">
            Before you send
          </span>
          People decide whether to accept based on your profile. It takes under a minute.
        </>
      }
    >
      <div className="flex items-baseline justify-between">
        <span className="text-mono text-muted font-mono uppercase">Skills you offer</span>
        <span role="status" className="text-mono text-ink font-mono">
          {Math.min(picked.length, GATE_SKILLS)} / {GATE_SKILLS}
        </span>
      </div>
      <div role="group" aria-label="Skills you offer" className="flex flex-wrap gap-2">
        {choices.map((skill) => (
          <ChoiceChip
            key={skill}
            pressed={includesTag(picked, skill)}
            onToggle={() => setPicked((current) => toggleTag(current, skill))}
          >
            {skill}
          </ChoiceChip>
        ))}
      </div>
      <SkillSearch
        label="Search more skills"
        placeholder="Search more skills"
        picked={picked}
        disabled={picked.length >= MAX_TAGS}
        onAdd={(skill) => setPicked((current) => toggleTag(current, skill))}
      />
      {error ? <InlineError announce>{error}</InlineError> : null}
      <div className="flex items-center justify-end gap-2 pt-1">
        <Button variant="ghost" disabled={busy} onClick={notNow}>
          Not now
        </Button>
        <Button variant="primary" disabled={busy || !enough} onClick={save}>
          Save and continue
        </Button>
      </div>
    </Dialog>
  );

  return { guard, dialog };
}
