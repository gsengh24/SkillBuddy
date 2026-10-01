import type { ReactNode } from "react";

import { hueStyle } from "@/lib/design/color";
import type { HueName } from "@/lib/design/tokens";

import { cx } from "./cx";

/** A small pill: the hue's edge border and ink text on paper. */
export function Tag({
  hue = "green",
  children,
  className,
}: {
  hue?: HueName;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      style={hueStyle(hue)}
      className={cx(
        "bg-paper text-small inline-flex items-center rounded-full border border-(--hue-edge) px-2.5 py-0.5 font-medium text-(--hue-ink)",
        className,
      )}
    >
      {children}
    </span>
  );
}

/** A filled suggestion pill: the hue's tint with its ink text (e.g. "Or try" prompts). */
export function TintPill({
  hue = "green",
  children,
  className,
}: {
  hue?: HueName;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      style={hueStyle(hue)}
      className={cx(
        "text-small inline-flex items-center rounded-full bg-(--hue-tint) px-3 py-1 font-medium text-(--hue-ink)",
        className,
      )}
    >
      {children}
    </span>
  );
}
