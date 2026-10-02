"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { IntentChip } from "@/components/ui/intent-chip";
import { TextArea } from "@/components/ui/text-field";
import { browserApi } from "@/lib/api/browser";
import { matchRequestSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { INTENTS, type Intent } from "@/lib/design/tokens";

const MIN = 10;
const MAX = 1000;

/** "What are you looking for?": an optional intent chip plus free text. */
export function RequestComposer() {
  const router = useRouter();
  const ids = useId();
  const [intent, setIntent] = useState<Intent | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const length = text.trim().length;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (length < MIN) {
      setError(`Say a little more: at least ${MIN} characters.`);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await browserApi("/requests", matchRequestSchema, {
        method: "POST",
        body: { text: text.trim(), intent },
      });
      setText("");
      setIntent(null);
      setStatus("Looking for matches…");
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      noValidate
      onSubmit={onSubmit}
      className="flex flex-col gap-4"
      aria-labelledby={`${ids}-h`}
    >
      <h2 id={`${ids}-h`} className="text-section">
        What are you looking for?
      </h2>
      <p role="status" aria-live="polite" className="sr-only">
        {status}
      </p>
      <fieldset className="flex flex-col gap-2">
        <legend className="text-small text-muted mb-1">Pick one, or just describe it</legend>
        <div className="flex flex-wrap gap-2">
          {INTENTS.map((value) => (
            <IntentChip
              key={value}
              intent={value}
              selected={intent === value}
              onToggle={() => setIntent(intent === value ? null : value)}
            />
          ))}
        </div>
      </fieldset>
      <TextArea
        id={`${ids}-text`}
        label="Describe it in your own words"
        hint={`${length}/${MAX} characters`}
        rows={4}
        maxLength={MAX}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="e.g. A designer to build a small budgeting app with, a few hours on weekends."
      />
      {error ? (
        <p
          role="alert"
          className="rounded-why bg-coral-tint text-small text-coral-ink px-4 py-3 font-semibold"
        >
          {error}
        </p>
      ) : null}
      <Button type="submit" disabled={submitting} className="self-start">
        {submitting ? "Sending…" : "Find matches"}
      </Button>
    </form>
  );
}
