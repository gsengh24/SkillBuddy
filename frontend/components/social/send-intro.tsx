"use client";

import { useId, useState, type FormEvent } from "react";

import { Button, ButtonLink } from "@/components/ui/button";
import { TextArea } from "@/components/ui/text-field";
import { browserApi } from "@/lib/api/browser";
import { introSchema, type Match } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import type { HueName } from "@/lib/design/tokens";

const NOTE_MAX = 500;

type Stage = "idle" | "writing" | "sent";

/**
 * "Send intro" on a match card: an optional short note, and a plain statement of what the
 * other person will see before they decide (ARCHITECTURE.md §8, two-sided consent).
 */
export function SendIntro({ match, hue }: { match: Match; hue: HueName }) {
  const ids = useId();
  const [stage, setStage] = useState<Stage>(
    match.status === "intro_sent" || match.status === "declined" ? "sent" : "idle",
  );
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  if (match.status === "accepted") {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-small text-ink font-semibold">You&apos;re connected.</span>
        <ButtonLink href="/messages" hue={hue}>
          Open Messages
        </ButtonLink>
      </div>
    );
  }

  if (stage === "sent") {
    return (
      <p role="status" className="text-small text-ink font-semibold">
        Intro sent. We&apos;ll let you know if they accept.
      </p>
    );
  }

  if (stage === "idle") {
    return (
      <Button type="button" hue={hue} onClick={() => setStage("writing")} className="self-start">
        Send intro
      </Button>
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSending(true);
    setError(null);
    try {
      await browserApi(`/matches/${match.id}/intro`, introSchema, {
        method: "POST",
        body: { note: note.trim() },
      });
      setStage("sent");
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setSending(false);
    }
  }

  return (
    <form
      noValidate
      onSubmit={onSubmit}
      className="flex flex-col gap-3"
      aria-labelledby={`${ids}-h`}
    >
      <p id={`${ids}-h`} className="text-small text-ink font-semibold">
        Send an intro
      </p>
      <TextArea
        id={`${ids}-note`}
        label="A short hello (optional)"
        hint={`${note.trim().length}/${NOTE_MAX} characters`}
        rows={3}
        maxLength={NOTE_MAX}
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder="e.g. Hi! I'm building a budgeting app and would love your design eye."
      />
      <p className="text-small text-muted">
        They&apos;ll see what you asked for, why you were matched and your note. Your name and links
        stay hidden unless they accept.
      </p>
      {error ? (
        <p role="alert" className="text-small text-coral-ink font-semibold">
          {error}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" hue={hue} disabled={sending}>
          {sending ? "Sending…" : "Send intro"}
        </Button>
        <Button type="button" onClick={() => setStage("idle")} disabled={sending}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
