"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";

import { cx } from "../ui/cx";
import { CheckIcon, PlusIcon } from "./icons";

/**
 * A chip you can tap on and off: a toggle button with aria-pressed, 44px tall on phones.
 * green (offers, interests): green outline with a dot, filled green when picked.
 * ink (wants): muted outline with a plus, ink edge and a tick when picked. Picking scales
 * it briefly (transform only; off with reduced motion).
 */
export function ChoiceChip({
  pressed,
  onToggle,
  tone = "green",
  children,
  label,
  className,
}: {
  pressed: boolean;
  onToggle: () => void;
  tone?: "green" | "ink";
  children: ReactNode;
  /** A fuller accessible name than the visible text, e.g. "Saturday" for "Sat". */
  label?: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      aria-label={label}
      onClick={onToggle}
      className={cx(
        "text-meta inline-flex min-h-11 items-center gap-2 rounded-full border px-3.5 font-mono font-medium tracking-[0.06em] uppercase pointer-fine:min-h-9",
        "transition-transform duration-200 ease-out active:scale-[.96] motion-reduce:transition-none motion-reduce:active:scale-100",
        tone === "green"
          ? pressed
            ? "border-green bg-green text-bg hover:border-green-hover hover:bg-green-hover"
            : "border-green text-green hover:border-green-hover hover:text-green-hover bg-transparent"
          : pressed
            ? "border-ink bg-line-strong text-ink"
            : "border-muted-2 text-ink-2 hover:border-ink hover:text-ink bg-transparent",
        className,
      )}
    >
      {tone === "green" ? (
        <span
          aria-hidden
          className={cx("size-1.5 shrink-0 rounded-full", pressed ? "bg-bg" : "bg-green")}
        />
      ) : pressed ? (
        <CheckIcon className="size-3.5 shrink-0" />
      ) : (
        <PlusIcon className="size-3.5 shrink-0" />
      )}
      {children}
    </button>
  );
}

/**
 * A large selectable card (onboarding step 1): icon, title, one line, and a tick in the
 * corner. A toggle button with aria-pressed; picked cards turn green tint.
 */
export function ChoiceCard({
  pressed,
  onToggle,
  icon,
  title,
  line,
}: {
  pressed: boolean;
  onToggle: () => void;
  icon: ReactNode;
  title: string;
  line: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onToggle}
      className={cx(
        "rounded-card relative grid min-h-[132px] content-start gap-1.5 border p-3.5 text-left",
        "transition-transform duration-200 ease-out active:scale-[.98] motion-reduce:transition-none motion-reduce:active:scale-100",
        pressed ? "border-green bg-green-tint" : "border-line-strong bg-card hover:border-muted-2",
      )}
    >
      <span
        aria-hidden
        className={cx(
          "absolute top-3 right-3 grid size-[22px] place-items-center rounded-full border",
          pressed ? "border-green bg-green text-bg" : "border-muted-2 text-transparent",
        )}
      >
        <CheckIcon className="size-[13px]" />
      </span>
      <span aria-hidden className="text-green mb-1.5">
        {icon}
      </span>
      <span className="text-title text-ink pr-7">{title}</span>
      <span className="text-meta text-muted">{line}</span>
    </button>
  );
}

/**
 * "Step n of 4" progress: a thin bar of segments, green up to the current step. Exposed as
 * a progressbar so screen readers hear where they are.
 */
export function StepProgress({
  step,
  total,
  label,
  className,
}: {
  step: number;
  total: number;
  /** The progressbar's accessible name, e.g. "Profile setup". */
  label: string;
  className?: string;
}) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={1}
      aria-valuemax={total}
      aria-valuenow={step}
      aria-valuetext={`Step ${step} of ${total}`}
      className={cx("grid gap-1", className)}
      style={{ gridTemplateColumns: `repeat(${total}, minmax(0, 1fr))` }}
    >
      {Array.from({ length: total }, (_, index) => (
        <i
          key={index}
          className={cx("h-[3px] rounded-[2px]", index < step ? "bg-green" : "bg-line")}
        />
      ))}
    </div>
  );
}

export type RadioOption<T extends string> = { value: T; label: string };

/**
 * A segmented single choice (year, hours a week) as a radiogroup: the arrow keys move and
 * pick, Tab enters at the picked option (or the first), like native radio buttons.
 */
export function RadioSegments<T extends string>({
  label,
  options,
  value,
  onChange,
  className,
}: {
  label: string;
  options: RadioOption<T>[];
  value: T | null;
  onChange: (value: T) => void;
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const current = options.findIndex((option) => option.value === value);

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const next = (index + step + options.length) % options.length;
    const option = options[next];
    if (!option) return;
    onChange(option.value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cx("bg-panel border-line flex gap-1 rounded-[10px] border p-1", className)}
    >
      {options.map((option, index) => {
        const checked = index === current;
        return (
          <button
            key={option.value}
            ref={(node) => {
              refs.current[index] = node;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked || (current === -1 && index === 0) ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cx(
              "text-meta-lg min-h-11 min-w-0 flex-1 rounded-[7px] border px-1.5 whitespace-nowrap pointer-fine:min-h-10",
              checked
                ? "border-line-strong bg-page-soft text-ink font-semibold"
                : "text-muted hover:text-ink border-transparent bg-transparent",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
