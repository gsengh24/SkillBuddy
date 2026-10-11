"use client";

import { useEffect, useId, useState } from "react";

import { cx } from "@/components/ui/cx";
import { MAX_PHRASES, PHRASE_MAX } from "@/lib/profile/limits";
import { SKILL_SUGGEST_DELAY_MS } from "@/lib/profile/skills";

/**
 * Tags with add-by-Enter and suggestions. "learn" tags are dashed, as in the reference.
 * Each tag has its own remove button.
 *
 * With `search`, typing shows matching names in a dropdown (a combobox: arrow keys move,
 * Enter picks, Escape closes). Enter with nothing highlighted still adds what was typed, so
 * a skill the list does not know is never blocked. While nothing is typed, `suggestions`
 * show as quick-add chips.
 */
export function TagEditor({
  label,
  inputLabel,
  placeholder,
  tags,
  suggestions,
  search,
  variant = "offer",
  onChange,
}: {
  label: string;
  inputLabel: string;
  placeholder: string;
  tags: string[];
  suggestions: string[];
  search?: (query: string) => Promise<string[]>;
  variant?: "offer" | "learn";
  onChange: (tags: string[]) => void;
}) {
  const ids = useId();
  const [text, setText] = useState("");
  const [found, setFound] = useState<string[]>([]);
  const [active, setActive] = useState(-1);
  const full = tags.length >= MAX_PHRASES;
  const has = (value: string) => tags.some((t) => t.toLowerCase() === value.toLowerCase());
  const options = found.filter((name) => !has(name));
  const open = options.length > 0 && !full;

  useEffect(() => {
    const query = text.trim();
    if (!search || !query) return;
    // Results arriving after the text moved on (or the editor went away) are dropped.
    let current = true;
    const timer = setTimeout(() => {
      search(query)
        .then((names) => {
          if (!current) return;
          setFound(names);
          setActive(-1);
        })
        .catch(() => {
          if (current) setFound([]);
        });
    }, SKILL_SUGGEST_DELAY_MS);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [text, search]);

  function change(value: string) {
    setText(value);
    if (!value.trim()) {
      setFound([]);
      setActive(-1);
    }
  }

  function add(value: string) {
    const clean = value.trim().slice(0, PHRASE_MAX);
    if (!clean || has(clean) || full) return;
    onChange([...tags, clean]);
  }

  function pick(value: string) {
    add(value);
    change("");
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
      <div className="relative">
        <input
          id={`${ids}-input`}
          role={search ? "combobox" : undefined}
          aria-expanded={search ? open : undefined}
          aria-controls={search && open ? `${ids}-list` : undefined}
          aria-autocomplete={search ? "list" : undefined}
          aria-activedescendant={open && active >= 0 ? `${ids}-option-${active}` : undefined}
          aria-label={inputLabel}
          aria-describedby={full ? `${ids}-full` : undefined}
          placeholder={placeholder}
          maxLength={PHRASE_MAX}
          disabled={full}
          autoComplete="off"
          value={text}
          onChange={(event) => change(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" && open) {
              event.preventDefault();
              setActive((i) => (i + 1) % options.length);
            } else if (event.key === "ArrowUp" && open) {
              event.preventDefault();
              setActive((i) => (i <= 0 ? options.length - 1 : i - 1));
            } else if (event.key === "Escape" && open) {
              event.preventDefault();
              setFound([]);
              setActive(-1);
            } else if (event.key === "Enter") {
              event.preventDefault();
              pick((open ? options[active] : undefined) ?? text);
            }
          }}
          className="rounded-input border-muted-2 bg-bg text-ink placeholder:text-muted focus:border-green sm:text-body disabled:bg-panel h-11 w-full border px-3 text-[16px]"
        />
        {open ? (
          <ul
            id={`${ids}-list`}
            role="listbox"
            aria-label={`${inputLabel}: suggestions`}
            className="rounded-input border-line bg-bg absolute inset-x-0 top-full z-10 mt-1 max-h-64 overflow-auto border py-1"
          >
            {options.map((name, index) => (
              <li
                key={name}
                id={`${ids}-option-${index}`}
                role="option"
                aria-selected={index === active}
                // Mouse down, not click: the input must not lose focus first.
                onMouseDown={(event) => {
                  event.preventDefault();
                  pick(name);
                }}
                className={cx(
                  "text-ink text-body flex min-h-11 cursor-pointer items-center px-3",
                  index === active ? "bg-panel" : "hover:bg-panel",
                )}
              >
                {name}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      {full ? (
        <p id={`${ids}-full`} className="text-meta text-muted">
          That&apos;s {MAX_PHRASES}, the most you can add. Remove one to add another.
        </p>
      ) : null}
      {!text && suggestions.some((s) => !has(s)) && !full ? (
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
