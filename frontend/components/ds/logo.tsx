import { brand } from "@/lib/brand";
import { colors } from "@/lib/design/tokens";

import { cx } from "../ui/cx";

/**
 * The logo: a placeholder four-dot mark (green and ink) and the lowercase wordmark. The
 * only place the logo is drawn, so the real SVG (frontend/public/logo.svg, when it
 * arrives) replaces it here. The supplied source, docs/design/cynergi-logo-source.jpeg,
 * is not used: its colours don't match the palette.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cx("text-ink inline-flex items-center gap-2", className)}>
      <svg aria-hidden focusable="false" viewBox="0 0 22 22" className="size-[22px] shrink-0">
        <circle cx="6" cy="6" r="3.5" fill={colors.green} />
        <circle cx="16" cy="6" r="3.5" fill={colors.ink} />
        <circle cx="6" cy="16" r="3.5" fill={colors.ink} />
        <circle cx="16" cy="16" r="3.5" fill={colors.green} />
      </svg>
      <span className="font-display text-[18px] leading-none font-extrabold tracking-[-0.04em] lowercase">
        {brand.wordmark}
      </span>
    </span>
  );
}
