import Link from "next/link";
import type { ComponentProps } from "react";

import { hueStyle } from "@/lib/design/color";
import type { HueName } from "@/lib/design/tokens";

import { cx } from "./cx";

export type ButtonTone = "ink" | "danger";

type ToneProps = {
  /** "ink" (default) or "danger" (coral ink, for destructive actions). */
  tone?: ButtonTone;
  /** Colour the outline and label with a hue's ink, e.g. a person's "Connect" button. */
  hue?: HueName;
};

/**
 * Thin outline pill: 1px border, transparent fill, never a bulky filled button. 44px high
 * by default (touch) and 38px on large screens with a fine pointer. Hover changes colour
 * only.
 */
export function buttonClasses({ tone = "ink", hue }: ToneProps = {}, className?: string): string {
  const colours = hue
    ? "border-(--hue-ink) text-(--hue-ink) hover:bg-(--hue-tint)"
    : tone === "danger"
      ? "border-coral-ink text-coral-ink hover:bg-coral-tint"
      : "border-ink text-ink hover:bg-green-chip";
  return cx(
    "inline-flex h-11 items-center justify-center gap-2 rounded-full border bg-transparent px-4",
    "text-[14px] leading-none font-semibold whitespace-nowrap lg:pointer-fine:h-[38px]",
    colours,
    "disabled:cursor-not-allowed disabled:border-line-strong disabled:text-muted disabled:hover:bg-transparent",
    className,
  );
}

export function Button({
  tone,
  hue,
  className,
  style,
  type = "button",
  ...props
}: ComponentProps<"button"> & ToneProps) {
  return (
    <button
      type={type}
      style={hue ? { ...hueStyle(hue), ...style } : style}
      className={buttonClasses({ tone, hue }, className)}
      {...props}
    />
  );
}

/** A link that looks like a Button (for navigation, not actions). */
export function ButtonLink({
  tone,
  hue,
  className,
  style,
  ...props
}: ComponentProps<typeof Link> & ToneProps) {
  return (
    <Link
      style={hue ? { ...hueStyle(hue), ...style } : style}
      className={buttonClasses({ tone, hue }, className)}
      {...props}
    />
  );
}
