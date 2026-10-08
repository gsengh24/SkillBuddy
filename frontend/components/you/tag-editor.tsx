"use client";

import { useId, useState } from "react";

import { cx } from "@/components/ui/cx";
import { MAX_PHRASES, PHRASE_MAX } from "@/lib/profile/limits";

/**
 * Tags with add-by-Enter and suggestions. "learn" tags are dashed, as in the reference.
 * Each tag has its own remove button; suggestions add on click.
 */
export function TagEditor({
  label,
  inputLabel,
  placeholder,
  tags,
  suggestions,
  variant = "offer",
  onChange,
}: {
  label: string;
  inputLabel: string;
  placeholder: string;
  tags: string[];
  suggestions: string[];
  variant?: "offer" | "learn";
  onChange: (tags: string[]) => void;
}) {
  const ids = useId();
  const [text, setText] = useState("");
  const full = tags.length >= MAX_PHRASES;
  const has = (value: string) => tags.some((t) => t.toLowerCase() === value.toLowerCase());

  function add(value: string) {
    const clean = value.trim().slice(0, PHRASE_MAX);
    if (!clean || has(clean) || full) return;
    onChange([...tags, clean]);
  }

  return (
    <div role="group" aria-labelledby={`${ids}-label`} className="flex flex-col gap-2">
      <span id={`${ids}-label`} className="text-meta-lg text-ink font-medium">
        {label}
      </span>
      {tags.length ? (
        <ul className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <li
              key={tag}
              className={cx(
                "text-green inline-flex min-h-8 items-center gap-1 rounded-full border pr-1 pl-3 text-[13px] font-medium",
                variant === "learn"
                  ? "border-green bg-bg border-dashed"
                  : "border-green-line bg-green-tint",
              )}
            >
              {tag}
              <button
                type="button"
                aria-label={`Remove ${tag}`}
                onClick={() => onChange(tags.filter((t) => t !== tag))}
                className="hover:bg-green-soft inline-flex size-7 items-center justify-center rounded-full text-[16px] leading-none"
              >
                <span aria-hidden>×</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <input
        id={`${ids}-input`}
        aria-label={inputLabel}
        aria-describedby={full ? `${ids}-full` : undefined}
        placeholder={placeholder}
        maxLength={PHRASE_MAX}
        disabled={full}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== "Enter") return;
          event.preventDefault();
          add(text);
          setText("");
        }}
        className="rounded-input border-muted-2 bg-bg text-ink placeholder:text-muted focus:border-green sm:text-body disabled:bg-panel h-11 w-full border px-3 text-[16px]"
      />
      {full ? (
        <p id={`${ids}-full`} className="text-meta text-muted">
          That&apos;s {MAX_PHRASES}, the most you can add. Remove one to add another.
        </p>
      ) : null}
      {suggestions.some((s) => !has(s)) && !full ? (
        <div className="flex flex-wrap gap-1.5">
          {suggestions
            .filter((s) => !has(s))
            .map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                aria-label={`Add ${suggestion}`}
                onClick={() => add(suggestion)}
                className="border-line text-ink-2 hover:bg-panel text-meta min-h-11 rounded-full border px-2.5 pointer-fine:min-h-[30px]"
              >
                + {suggestion}
              </button>
            ))}
        </div>
      ) : null}
    </div>
  );
}
