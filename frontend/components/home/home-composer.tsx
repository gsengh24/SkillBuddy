"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { InlineError } from "@/components/ds/fields";
import { cx } from "@/components/ui/cx";
import { browserApi } from "@/lib/api/browser";
import { matchRequestSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { INTENTS, intents, type Intent } from "@/lib/design/tokens";
import { itemHref } from "@/lib/home/activity";
import { notifyHomeChanged } from "@/lib/home/changed";

const MIN = 10;
// The request limit the API and the old composer use.
const MAX = 1000;

/** One line under the chips about the picked kind of help. */
const HINTS: Record<Intent, string> = {
  build_together: "Find someone to ship a project with you.",
  skill_exchange: "Swap what you know for what you want to learn.",
  interest_buddy: "Meet someone into the same topic, at the same depth.",
  accountability: "Someone at your stage to keep you both on track.",
  mentor: "Someone further along who wants to help.",
  explore: "A few interesting people, with a little serendipity.",
};

/** Typed into the empty box once, then it rests on the first line. */
const EXAMPLES = [
  "I'm building a budgeting app and need a design eye.",
  "Looking for a teammate for a hackathon.",
  "Teach me Figma, I can teach Python.",
  "Want an accountability partner for my side project.",
];

const TRY: { text: string; intent: Intent }[] = [
  { text: "Need a teammate for a hackathon", intent: "build_together" },
  { text: "Teach me Figma, I can teach Python", intent: "skill_exchange" },
];

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
        "inline-flex min-h-11 items-center gap-2 rounded-full border px-3.5 text-[14px] lg:hover:-translate-y-0.5 pointer-fine:min-h-10",
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
 * The typed placeholder: it runs through the examples once while the box is empty and
 * unfocused, then rests on the first one. With reduced motion it only shows the first.
 */
function useTypedPlaceholder(active: boolean): { text: string; typing: boolean } {
  const [state, setState] = useState({ text: EXAMPLES[0] ?? "", typing: false });
  const done = useRef(false);

  useEffect(() => {
    if (!active || done.current) return;
    if (typeof window.matchMedia !== "function") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let example = 0;
    let length = 0;
    let deleting = false;
    let timer = 0;
    const tick = () => {
      const target = EXAMPLES[example] ?? "";
      if (!deleting) {
        length += 1;
        if (length >= target.length) {
          if (example === EXAMPLES.length - 1) {
            done.current = true;
            setState({ text: EXAMPLES[0] ?? "", typing: false });
            return;
          }
          deleting = true;
          setState({ text: target, typing: true });
          timer = window.setTimeout(tick, 1500);
          return;
        }
      } else {
        length -= 2;
        if (length <= 0) {
          length = 0;
          deleting = false;
          example += 1;
        }
      }
      setState({ text: target.slice(0, Math.max(length, 0)), typing: true });
      timer = window.setTimeout(tick, deleting ? 16 : 40);
    };
    timer = window.setTimeout(tick, 900);
    return () => {
      window.clearTimeout(timer);
      setState({ text: EXAMPLES[0] ?? "", typing: false });
    };
  }, [active]);

  return state;
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
  const textRef = useRef<HTMLTextAreaElement>(null);
  const [intent, setIntent] = useState<Intent | null>(null);
  const [text, setText] = useState("");
  const [opened, setOpened] = useState(false);
  const [focused, setFocused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const length = text.trim().length;
  const open = opened || intent !== null || text.length > 0;
  const placeholder = useTypedPlaceholder(text.length === 0 && !focused);

  function fill(example: { text: string; intent: Intent }) {
    setText(example.text);
    setIntent(example.intent);
    setError(null);
    textRef.current?.focus();
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (length < MIN) {
      setError(`Say a little more: at least ${MIN} characters.`);
      setOpened(true);
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
      // Open the new request: it shows its matches as they arrive. The inbox does not know it
      // yet, so it re-fetches its lists (queued after the navigation, so it sees the new item).
      router.push(itemHref("request", created.id));
      notifyHomeChanged();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <form
        noValidate
        onSubmit={onSubmit}
        aria-label="New request"
        data-open={open}
        className="bg-green-tint border-green-line rounded-[16px] border p-3.5 lg:p-[22px]"
      >
        <p role="status" aria-live="polite" className="sr-only">
          {status}
        </p>
        <label
          htmlFor={`${ids}-text`}
          className="text-green mb-2 hidden font-mono text-[11px] leading-[1.4] font-medium tracking-[0.08em] uppercase lg:block"
        >
          <span className="sr-only">Describe it in your own words. </span>
          Your request
        </label>
        <div className="border-ink bg-bg relative rounded-xl border-[1.5px] focus-within:shadow-[0_0_0_4px_rgb(15_74_52/0.15)]">
          {text.length === 0 ? (
            <div
              aria-hidden
              className="text-muted pointer-events-none absolute inset-x-4 top-3.5 text-[16px] leading-[1.45] lg:text-[17px]"
            >
              {placeholder.text}
              {placeholder.typing ? (
                <span className="bg-green ml-0.5 inline-block h-[1.05em] w-0.5 align-[-0.16em]" />
              ) : null}
            </div>
          ) : null}
          <textarea
            id={`${ids}-text`}
            ref={textRef}
            rows={3}
            maxLength={MAX}
            value={text}
            aria-label="Describe it in your own words"
            aria-describedby={`${ids}-count`}
            onFocus={() => {
              setOpened(true);
              setFocused(true);
            }}
            onBlur={() => setFocused(false)}
            onChange={(event) => setText(event.target.value)}
            className="block min-h-[78px] w-full resize-y rounded-xl bg-transparent px-4 py-3.5 text-[16px] leading-[1.45] outline-none focus-visible:shadow-none lg:min-h-[104px] lg:text-[17px]"
          />
        </div>
        <fieldset
          className={cx(
            "m-0 mt-[18px] min-w-0 border-0 p-0",
            open ? "flex flex-col" : "hidden lg:flex lg:flex-col",
          )}
        >
          <legend className="text-green mb-2.5 block w-full p-0 font-mono text-[11px] leading-[1.4] font-medium tracking-[0.08em] uppercase">
            What kind of help
          </legend>
          <div className="flex flex-wrap gap-2">
            {INTENTS.map((value) => (
              <IntentToggle
                key={value}
                intent={value}
                selected={intent === value}
                onToggle={() => setIntent(intent === value ? null : value)}
              />
            ))}
          </div>
          <p className="text-ink-2 mt-2.5 min-h-[1.5em] text-[13.5px]">
            {intent ? HINTS[intent] : null}
          </p>
        </fieldset>
        {error ? <InlineError announce>{error}</InlineError> : null}
        <div className={cx("flex items-center justify-between gap-3", open ? "mt-[18px]" : "mt-3")}>
          <span
            id={`${ids}-count`}
            aria-hidden
            className={cx(
              "text-muted font-mono text-[11px] tracking-[0.08em] tabular-nums",
              open ? "block" : "hidden lg:block",
            )}
          >
            {text.length} / {MAX}
          </span>
          <button
            type="submit"
            disabled={submitting}
            className="bg-ink text-bg hover:bg-ink-hover disabled:bg-panel disabled:text-muted inline-flex min-h-12 flex-1 items-center justify-center rounded-xl px-[22px] text-[15px] font-semibold transition-transform active:scale-[.97] disabled:cursor-not-allowed lg:flex-none lg:hover:-translate-y-0.5"
          >
            {submitting ? "Sending…" : "Find matches"}
          </button>
        </div>
      </form>
      <p className="text-muted mt-4 hidden flex-wrap gap-x-[18px] gap-y-1.5 px-0.5 text-[14px] lg:flex">
        Try:{" "}
        {TRY.map((example) => (
          <button
            key={example.text}
            type="button"
            onClick={() => fill(example)}
            className="text-ink border-muted-2 border-b"
          >
            {example.text}
          </button>
        ))}
      </p>
    </>
  );
}
