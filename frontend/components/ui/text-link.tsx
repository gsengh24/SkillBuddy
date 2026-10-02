import Link from "next/link";
import type { ComponentProps } from "react";

import { cx } from "./cx";

/** Inline link: green ink, underlined; hover darkens to ink. */
export function textLinkClasses(tone: "green" | "muted" = "green", className?: string): string {
  return cx(
    "font-semibold underline decoration-1 underline-offset-2",
    tone === "green" ? "text-green-ink hover:text-ink" : "text-muted hover:text-ink",
    className,
  );
}

export function TextLink({
  tone,
  className,
  ...props
}: ComponentProps<typeof Link> & { tone?: "green" | "muted" }) {
  return <Link className={textLinkClasses(tone, className)} {...props} />;
}
