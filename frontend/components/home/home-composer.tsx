"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { InlineError, Textarea } from "@/components/ds/fields";
import { cx } from "@/components/ui/cx";
import { browserApi } from "@/lib/api/browser";
import { matchRequestSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { INTENTS, intents, type Intent } from "@/lib/design/tokens";
import { itemHref } from "@/lib/home/activity";

const MIN = 10;
// The request limit the API and the old composer use.
const MAX = 1000;

/** One intent as a pill: a green dot on every chip; selected is filled green with a mint dot. */
function IntentToggle({
  intent,
  selected,
  onToggle,
}: {
  intent: Intent;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onToggle}
      className={cx(
        "text-meta-lg inline-flex min-h-11 items-center gap-2 rounded-full border px-3 font-medium pointer-fine:min-h-9",
        selected
          ? "bg-green border-green text-bg"
          : "border-green-line bg-bg text-ink lg:hover:bg-green-soft",
      )}
    >
      <span
        aria-hidden
        className={cx("size-[7px] shrink-0 rounded-full", selected ? "bg-mint" : "bg-green")}
      />
      {intents[intent].label}
    </button>
  );
}

/**
 * The new-request composer on green tint (design spec 6.2, v2): the text first, then "What
 * kind of help" and the counter, then "Find matches". On phones the card starts collapsed
 * (text and button only) and opens when the text gets focus; it stays open after that, so
 * a tap on a chip is never lost. Behaviour, options and limits are as before. After
 * sending, the new request opens in the detail pane.
 */
export function HomeComposer() {
  const router = useRouter();
  const ids = useId();
  const [intent, setIntent] = useState<Intent | null>(null);
  const [text, setText] = useState("");
  const [opened, setOpened] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const length = text.trim().length;
  const open = opened || intent !== null || text.length > 0;

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
      aria-label="New request"
      data-open={open}
      className="bg-green-tint border-green-line rounded-panel mt-4 flex flex-col gap-3 border p-3 lg:mt-6 lg:p-4"
    >
      <p role="status" aria-live="polite" className="sr-only">
        {status}
      </p>
      <Textarea
        id={`${ids}-text`}
        label="Describe it in your own words"
        hideLabel
        rows={3}
        maxLength={MAX}
        showCounter={false}
        value={text}
        onFocus={() => setOpened(true)}
        onChange={(event) => setText(event.target.value)}
        placeholder="I'm building a budgeting app and need a design eye."
        className="border-green-line lg:min-h-24"
      />
      <fieldset className={cx("flex-col gap-2", open ? "flex" : "hidden lg:flex")}>
        <legend className="text-mono text-green mb-2 font-mono uppercase">What kind of help</legend>
        <div className="flex flex-wrap gap-1.5">
          {INTENTS.map((value) => (
            <IntentToggle
              key={value}
              intent={value}
              selected={intent === value}
              onToggle={() => setIntent(intent === value ? null : value)}
            />
          ))}
        </div>
      </fieldset>
      {error ? <InlineError announce>{error}</InlineError> : null}
      <div className="flex items-center justify-between gap-3">
        <span
          aria-hidden
          className={cx("text-mono text-muted font-mono", open ? "block" : "hidden lg:block")}
        >
          {text.length}/{MAX}
        </span>
        <Button type="submit" variant="primary" disabled={submitting} className="ml-auto">
          {submitting ? "Sending…" : "Find matches"}
        </Button>
      </div>
    </form>
  );
}
