import type { ComponentProps, CSSProperties, ReactNode } from "react";

import { cx } from "../ui/cx";

const PANEL_TONES = {
  white: "border-line bg-bg",
  panel: "border-line bg-panel",
  green: "border-green-line bg-green-tint",
} as const;

/**
 * A bordered panel: 1px line, radius 14, padding 16 on phones and 24 on desktop. With
 * `interactive`, its border turns green-line on hover (desktop).
 */
export function Panel({
  tone = "white",
  interactive = false,
  className,
  ...props
}: ComponentProps<"div"> & { tone?: keyof typeof PANEL_TONES; interactive?: boolean }) {
  return (
    <div
      className={cx(
        "rounded-panel border p-4 lg:p-6",
        PANEL_TONES[tone],
        interactive && "lg:hover:border-green-line",
        className,
      )}
      {...props}
    />
  );
}

/** Black label chip with a leading star, for cards: "* Safe by default". */
export function LabelChip({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        "bg-ink text-bg rounded-chip text-mono inline-flex items-center gap-1 px-[7px] py-[3px] font-mono uppercase",
        className,
      )}
    >
      <span aria-hidden>*</span>
      {children}
    </span>
  );
}

/**
 * A topic pill in mono. outline: green border on white (topics). soft: green-soft fill
 * (eyebrows on the green hero).
 */
export function TopicChip({
  tone = "outline",
  children,
  className,
}: {
  tone?: "outline" | "soft";
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "text-mono-lg inline-flex items-center px-2.5 py-[3px] font-mono",
        tone === "outline"
          ? "border-green bg-bg text-green rounded-full border"
          : "border-green-line bg-green-soft text-green rounded-[7px] border",
        className,
      )}
    >
      {children}
    </span>
  );
}

const STATUS = {
  request: { label: "Request", classes: "bg-ink text-bg border-ink" },
  intro: { label: "Intro", classes: "bg-green-tint text-green border-green-line" },
} as const;

/** A row's kind: REQUEST (black) or INTRO (green tint). Mono, uppercase. */
export function StatusBadge({
  kind,
  className,
}: {
  kind: keyof typeof STATUS;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "rounded-chip text-mono inline-flex h-fit items-center border px-1.5 py-0.5 font-mono uppercase",
        STATUS[kind].classes,
        className,
      )}
    >
      {STATUS[kind].label}
    </span>
  );
}

/** A loading placeholder block on panel, with a slow opacity pulse. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("bg-panel animate-pulse-soft rounded-card", className)} />;
}

/** Wraps skeletons so screen readers hear one "Loading" while they show. */
export function SkeletonGroup({
  label = "Loading",
  className,
  children,
}: {
  label?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div role="status" className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

/**
 * Numbered feature rows: a faint mono numeral (decorative, drawn by CSS so it is never
 * read or checked as text), then a bold lead word and the rest. The rest is `muted`, not
 * the reference's muted-2: at this size muted-2 fails 4.5:1.
 */
export function NumberedRows({
  rows,
  className,
}: {
  rows: { lead: string; rest: string }[];
  className?: string;
}) {
  return (
    <ol className={cx("border-line max-w-[720px] border-t", className)}>
      {rows.map((row, index) => (
        <li
          key={row.lead}
          data-n={String(index + 1).padStart(2, "0")}
          className="border-line text-body-lg before:text-faint flex items-baseline gap-3.5 border-b py-3.5 before:font-mono before:text-[13px] before:content-[attr(data-n)] lg:py-[18px] lg:text-[20px]"
        >
          <span>
            <strong className="text-ink font-extrabold">{row.lead}</strong>{" "}
            <span className="text-muted">{row.rest}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

/** The hero grid: bordered cells on green tint, holding real product pieces. */
export function HeroGrid({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cx(
        "border-green-line grid grid-cols-2 border-t lg:grid-rows-3 lg:border-t-0 lg:border-l",
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * One hero cell. Cells fade up one after another on load, 70ms apart (8 cells at most);
 * reduced motion shows them at once.
 */
export function HeroCell({
  index,
  wide = false,
  className,
  children,
}: {
  index: number;
  wide?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const style: CSSProperties = { animationDelay: `${50 + Math.min(index, 7) * 70}ms` };
  return (
    <div
      style={style}
      className={cx(
        "animate-fade-up border-green-line flex min-h-[84px] items-center border-b p-2.5 lg:min-h-[130px]",
        wide
          ? "bg-bg col-span-2 justify-start px-4 py-3"
          : "justify-center border-r even:border-r-0",
        className,
      )}
    >
      {children}
    </div>
  );
}
