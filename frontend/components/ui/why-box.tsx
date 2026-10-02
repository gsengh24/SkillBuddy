import type { ReactNode } from "react";

import { hueStyle } from "@/lib/design/color";
import type { HueName } from "@/lib/design/tokens";

import { cx } from "./cx";

type WhyBoxProps = { hue?: HueName; title?: string; children: ReactNode; className?: string };

/** The reason for a match, on the hue's tint (radius 12). Title in the hue's ink. */
export function WhyBox({ hue = "green", title = "Why you two", children, className }: WhyBoxProps) {
  return (
    <div
      style={hueStyle(hue)}
      className={cx("rounded-why flex flex-col gap-1.5 bg-(--hue-tint) px-4 py-3", className)}
    >
      <p className="text-label font-mono font-medium text-(--hue-ink) uppercase">{title}</p>
      <div className="text-body text-ink">{children}</div>
    </div>
  );
}
