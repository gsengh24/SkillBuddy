"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { InlineError, Textarea } from "@/components/ds/fields";
import { IntentChip } from "@/components/ui/intent-chip";
import { browserApi } from "@/lib/api/browser";
import { matchRequestSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { INTENTS, type Intent } from "@/lib/design/tokens";
import { itemHref } from "@/lib/home/activity";

const MIN = 10;
// The request limit the API and the old composer use (1000); see the PR note.
const MAX = 1000;

/** Static examples. Tapping one fills the box; it never sends anything. */
export const SUGGESTIONS = ["a design partner", "learn React", "a study group", "co-founder"];

/**
 * The new-request composer on green tint: an optional intent, the text, a counter, "Find
 * matches", and suggestion pills. After sending, the new request opens in the detail pane.
 */
export function HomeComposer() {
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
      const created = await browserApi("/requests", matchRequestSchema, {
        method: "POST",
        body: { text: text.trim(), intent },
      });
      setText("");
      setIntent(null);
      setStatus("Looking for matches…");
      // Open the new request: it shows its matches as they arrive.
      router.push(itemHref("request", created.id));
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
      aria-labelledby={`${ids}-h`}
      className="bg-green-tint border-green-line rounded-panel flex flex-col gap-3 border p-3 lg:p-4"
    >
      <h2 id={`${ids}-h`} className="text-mono text-green font-mono uppercase">
        New request
      </h2>
      <p role="status" aria-live="polite" className="sr-only">
        {status}
      </p>
      <fieldset className="flex flex-col gap-2">
        <legend className="text-meta text-ink-2 mb-1">Pick one, or just describe it</legend>
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
      <Textarea
        id={`${ids}-text`}
        label="Describe it in your own words"
        hideLabel
        rows={3}
        maxLength={MAX}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="I'm building a budgeting app and need a design eye."
      />
      {error ? <InlineError announce>{error}</InlineError> : null}
      <div className="flex justify-end">
        <Button type="submit" variant="primary" disabled={submitting}>
          {submitting ? "Sending…" : "Find matches"}
        </Button>
      </div>
      <div role="group" aria-label="Try one of these" className="flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((phrase) => (
          <button
            key={phrase}
            type="button"
            onClick={() => setText(phrase)}
            className="border-green text-green bg-bg hover:bg-green-tint text-mono-lg min-h-11 rounded-full border px-3 font-mono pointer-fine:min-h-8"
          >
            {phrase}
          </button>
        ))}
      </div>
    </form>
  );
}
