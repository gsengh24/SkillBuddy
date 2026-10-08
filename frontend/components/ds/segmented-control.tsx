"use client";

import { cx } from "../ui/cx";

export type Segment<T extends string> = { value: T; label: string; count?: number };

/**
 * A segmented filter (All, Requests, Messages): a panel track with the selected segment in
 * white. Each segment is a toggle button with aria-pressed; Tab moves between them.
 */
export function SegmentedControl<T extends string>({
  label,
  segments,
  value,
  onChange,
  className,
}: {
  /** The group's accessible name, e.g. "Filter". */
  label: string;
  segments: Segment<T>[];
  /** null: nothing picked yet. */
  value: T | null;
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cx("bg-panel border-line flex gap-1 rounded-[10px] border p-[3px]", className)}
    >
      {segments.map((segment) => {
        const pressed = segment.value === value;
        return (
          <button
            key={segment.value}
            type="button"
            aria-pressed={pressed}
            onClick={() => onChange(segment.value)}
            className={cx(
              "text-meta min-h-11 flex-1 rounded-lg border px-2 pointer-fine:min-h-9",
              pressed
                ? "border-line bg-bg text-ink font-medium"
                : "text-muted hover:text-ink border-transparent bg-transparent",
            )}
          >
            {segment.label}
            {segment.count === undefined ? null : ` ${segment.count}`}
          </button>
        );
      })}
    </div>
  );
}
