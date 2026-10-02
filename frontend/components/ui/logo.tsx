import { brand } from "@/lib/brand";
import { hues } from "@/lib/design/tokens";

import { cx } from "./cx";

/** Two overlapping rings (green and amber) and the wordmark. */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-2", className)}>
      <svg aria-hidden focusable="false" viewBox="0 0 32 22" fill="none" className="h-5 w-7">
        <circle cx="11" cy="11" r="8.5" stroke={hues.green.base} strokeWidth="2" />
        <circle cx="21" cy="11" r="8.5" stroke={hues.amber.base} strokeWidth="2" />
      </svg>
      <span className="text-ink text-[17px] font-bold tracking-[-0.01em]">{brand.name}</span>
    </span>
  );
}
