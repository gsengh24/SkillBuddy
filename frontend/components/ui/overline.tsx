import type { ComponentProps } from "react";

import { cx } from "./cx";

/** Small uppercase label in IBM Plex Mono (11px, wide letter-spacing). */
export function Overline({
  tone = "muted",
  className,
  ...props
}: ComponentProps<"p"> & { tone?: "muted" | "green" }) {
  return (
    <p
      className={cx(
        "text-label font-mono font-medium uppercase",
        tone === "green" ? "text-green-ink" : "text-muted",
        className,
      )}
      {...props}
    />
  );
}
