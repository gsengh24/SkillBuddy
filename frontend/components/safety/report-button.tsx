"use client";

import { useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { Textarea } from "@/components/ds/fields";
import { cx } from "@/components/ui/cx";
import { browserApi } from "@/lib/api/browser";
import { reportReceiptSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { REPORT_DETAILS_MAX_LENGTH, REPORT_REASONS, type ReportReason } from "@/lib/safety/reasons";

import { BlockButton } from "./block-button";

export type ReportKind = "message" | "intro" | "profile" | "goal" | "note";

const PATHS: Record<ReportKind, (id: string) => `/${string}`> = {
  message: (id) => `/messages/${id}/report`,
  intro: (id) => `/intros/${id}/report`,
  profile: (id) => `/people/${id}/report`,
  goal: (id) => `/space-goals/${id}/report`,
  note: (id) => `/progress-logs/${id}/report`,
};

const WHAT_IS_SEEN: Record<ReportKind, string> = {
  message: "Our moderator will see a copy of this message and the 10 messages before it.",
  intro: "Our moderator will see a copy of this intro: what they asked for and their note.",
  profile: "Our moderator will see a copy of their profile as you can see it.",
  goal: "Our moderator will see a copy of this goal.",
  note: "Our moderator will see a copy of this note.",
};

/**
 * Report a message, an intro or a profile. Says what the moderator will see, then offers
 * to block the person too. The reported person is never told.
 */
export function ReportButton({
  kind,
  targetId,
  blockUserId,
  blockName = "this person",
  compact = false,
}: {
  kind: ReportKind;
  targetId: string;
  /** Offer "Block them too" after reporting. */
  blockUserId?: string;
  blockName?: string;
  /** A small text button (under a chat message) instead of an outline button. */
  compact?: boolean;
}) {
  const ids = useId();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!reason) return;
    setBusy(true);
    setError(null);
    try {
      await browserApi(PATHS[kind](targetId), reportReceiptSchema, {
        method: "POST",
        body: { reason, details: details.trim() },
      });
      setDone(true);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div role="status" className="flex flex-col gap-3">
        <p className="text-meta-lg text-ink font-medium">
          Thanks. We&apos;ve received your report. They won&apos;t be told who reported them.
        </p>
        {blockUserId ? <BlockButton userId={blockUserId} name={blockName} /> : null}
      </div>
    );
  }

  if (!open) {
    return compact ? (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-meta-lg text-muted hover:text-ink min-h-11 font-medium underline decoration-1 underline-offset-2 lg:pointer-fine:min-h-0"
      >
        Report
      </button>
    ) : (
      <Button variant="outline" onClick={() => setOpen(true)}>
        Report
      </Button>
    );
  }

  return (
    <form
      onSubmit={submit}
      aria-labelledby={`${ids}-title`}
      className="border-line rounded-panel bg-bg flex w-full max-w-lg flex-col gap-3 border p-4"
    >
      <p id={`${ids}-title`} className="text-title text-ink">
        Report this {kind}
      </p>
      <p className="text-meta-lg text-ink-2">
        {WHAT_IS_SEEN[kind]} They won&apos;t be told who reported them.
      </p>
      <fieldset className="flex flex-col gap-1">
        <legend className="text-meta-lg text-ink mb-1 font-medium">What&apos;s wrong?</legend>
        {REPORT_REASONS.map((option) => (
          <label
            key={option.value}
            className={cx("flex min-h-11 items-center gap-3", "lg:pointer-fine:min-h-8")}
          >
            <input
              type="radio"
              name={`${ids}-reason`}
              value={option.value}
              checked={reason === option.value}
              onChange={() => setReason(option.value)}
              className="accent-green size-4"
            />
            <span>{option.label}</span>
          </label>
        ))}
      </fieldset>
      <Textarea
        label="Anything else the moderator should know? (optional)"
        rows={2}
        maxLength={REPORT_DETAILS_MAX_LENGTH}
        showCounter={false}
        value={details}
        onChange={(event) => setDetails(event.target.value)}
        error={error}
      />
      <div className="flex flex-wrap gap-3">
        <Button type="submit" variant="danger" disabled={busy || !reason}>
          {busy ? "Sending…" : "Send report"}
        </Button>
        <Button variant="ghost" disabled={busy} onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
