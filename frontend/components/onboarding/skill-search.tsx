"use client";

import { useEffect, useId, useState } from "react";

import { SearchIcon } from "@/components/ds/icons";
import { cx } from "@/components/ui/cx";
import { includesTag, TAG_MAX } from "@/lib/onboarding/catalog";
import { searchSkills, SKILL_SUGGEST_DELAY_MS } from "@/lib/profile/skills";

/**
 * Search for a skill that isn't on the chips (ADR 0020: suggest, don't force). A combobox:
 * typing shows matching names from GET /skills/suggest, arrow keys move, Enter picks the
 * highlighted name or adds what was typed, Escape closes. A failed search just shows none.
 */
export function SkillSearch({
  label,
  placeholder,
  picked,
  disabled,
  onAdd,
  search = searchSkills,
}: {
  label: string;
  placeholder: string;
  picked: readonly string[];
  disabled?: boolean;
  onAdd: (skill: string) => void;
  search?: (query: string) => Promise<string[]>;
}) {
  const ids = useId();
  const [text, setText] = useState("");
  const [found, setFound] = useState<string[]>([]);
  const [active, setActive] = useState(-1);
  const options = found.filter((name) => !includesTag(picked, name));
  const open = options.length > 0 && text.trim().length > 0;

  useEffect(() => {
    const query = text.trim();
    if (!query) return;
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

  function pick(value: string) {
    const clean = value.trim().slice(0, TAG_MAX);
    if (clean) onAdd(clean);
    setText("");
    setFound([]);
    setActive(-1);
  }

  return (
    <div className="relative">
      <SearchIcon className="text-muted pointer-events-none absolute top-1/2 left-3 size-[18px] -translate-y-1/2" />
      <input
        type="search"
        role="combobox"
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? `${ids}-list` : undefined}
        aria-autocomplete="list"
        aria-activedescendant={open && active >= 0 ? `${ids}-option-${active}` : undefined}
        placeholder={placeholder}
        maxLength={TAG_MAX}
        disabled={disabled}
        autoComplete="off"
        value={text}
        onChange={(event) => setText(event.target.value)}
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
        className="rounded-input border-muted-2 bg-card text-ink placeholder:text-muted focus:border-green sm:text-body disabled:bg-panel h-11 w-full border pr-3 pl-10 text-[16px]"
      />
      {open ? (
        <ul
          id={`${ids}-list`}
          role="listbox"
          aria-label={`${label}: suggestions`}
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
  );
}
