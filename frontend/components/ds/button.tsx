import Link from "next/link";
import type { ComponentProps } from "react";

import { cx } from "../ui/cx";

export type ButtonVariant = "primary" | "outline" | "ghost" | "white" | "danger";
export type ButtonSize = "default" | "compact";

type StyleProps = {
  /**
   * primary: ink fill, white text (at most one per view). outline: green border and text.
   * ghost: no border. white: for the green CTA band. danger: red outline, for destructive
   * confirmations.
   */
  variant?: ButtonVariant;
  /** compact is 36px high with a mouse; on touch screens every button stays 44px. */
  size?: ButtonSize;
};

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "border-transparent bg-ink text-bg hover:bg-ink-hover",
  outline: "border-green bg-transparent text-green hover:border-green-hover hover:text-green-hover",
  ghost: "border-transparent bg-transparent text-ink hover:bg-panel",
  white: "border-transparent bg-bg text-ink hover:bg-panel",
  danger: "border-danger bg-transparent text-danger hover:bg-panel",
};

const SIZES: Record<ButtonSize, string> = {
  default: "h-11 px-4 text-[13px] pointer-fine:h-10 lg:h-11 lg:px-[18px] lg:text-[14px]",
  compact: "h-11 px-3 text-[13px] pointer-fine:h-9",
};

/**
 * Lifts 2px on hover (desktop, mouse) and presses to 97%. Transform only; reduced motion
 * turns it off.
 */
export function buttonClasses(
  { variant = "outline", size = "default" }: StyleProps = {},
  className?: string,
): string {
  return cx(
    "rounded-control inline-flex items-center justify-center gap-2 border font-medium whitespace-nowrap",
    "transition-transform duration-150 ease-out active:scale-[.97] lg:hover:-translate-y-0.5",
    "disabled:border-line-strong disabled:bg-panel disabled:text-muted disabled:cursor-not-allowed disabled:active:scale-100 disabled:lg:hover:translate-y-0",
    SIZES[size],
    VARIANTS[variant],
    className,
  );
}

export function Button({
  variant,
  size,
  className,
  type = "button",
  ...props
}: ComponentProps<"button"> & StyleProps) {
  return <button type={type} className={buttonClasses({ variant, size }, className)} {...props} />;
}

/** A link that looks like a Button (for navigation, not actions). */
export function ButtonLink({
  variant,
  size,
  className,
  ...props
}: ComponentProps<typeof Link> & StyleProps) {
  return <Link className={buttonClasses({ variant, size }, className)} {...props} />;
}
